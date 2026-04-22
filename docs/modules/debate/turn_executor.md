# TurnExecutor

> 단일 턴 실행기 — LLM 스트리밍·WebSocket 발언 생성, Tool-Use 2단계 파이프라인, 재시도 로직 캡슐화

**파일 경로:** `backend/app/services/debate/turn_executor.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

`_execute_turn` / `_execute_turn_with_retry`로 분산되어 있던 단일 턴 실행 로직을 `TurnExecutor` 클래스로 캡슐화한다. 하나의 클래스가 다음 세 가지 책임을 완결한다.

1. **provider 분기** — `local` 에이전트는 WebSocket 경유, 그 외(OpenAI/Anthropic/Google/RunPod)는 LLM BYOK 스트리밍으로 처리
2. **Tool-Use 2단계 파이프라인** — `web_search` function call 감지 → 증거 검색 → 검색 결과를 대화 컨텍스트에 주입 → 스트리밍 발언 생성
3. **재시도 및 에러 격리** — `APIKeyError`는 1회 재시도 후 `MatchVoidError` 변환, 그 외 예외는 `debate_turn_max_retries` 횟수까지 재시도 후 `None` 반환

---

## 클래스: TurnExecutor

### 생성자

```python
def __init__(self, client: InferenceClient, db: AsyncSession) -> None:
    self.client = client
    self.db = db
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `client` | `InferenceClient` | provider별 LLM 호출 단일 진입점 |
| `db` | `AsyncSession` | SQLAlchemy 비동기 세션 (턴 로그 flush 용도) |

---

### 주요 메서드

#### `execute()` — 단일 턴 실행

```python
async def execute(
    match: DebateMatch,
    topic: DebateTopic,
    turn_number: int,
    speaker: str,
    agent: DebateAgent,
    version: DebateAgentVersion | None,
    api_key: str,
    my_claims: list[str],
    opponent_claims: list[str],
    my_accumulated_penalty: int = 0,
    event_meta: dict | None = None,
) -> DebateTurnLog
```

**동작 흐름:**

```
agent.provider == "local"?
├─ Yes → WSConnectionManager.request_turn() 대기 (asyncio.wait_for)
│        → turn_chunk SSE 단일 청크 발행 (타이핑 애니메이션 활성화)
└─ No  → Tool-Use 2단계 파이프라인 or 스트리밍 직행
         → validate_response_schema() 파싱
         → DebateTurnLog flush → return
```

**반환값:** DB에 `flush()`된 `DebateTurnLog` 인스턴스 (아직 commit 되지 않음)

**예외:** 모든 예외를 그대로 전파한다. 재시도 판단은 `execute_with_retry()`가 담당한다.

| 예외 | 발생 조건 |
|---|---|
| `TimeoutError` | 턴 타임아웃 초과 (`debate_turn_timeout_seconds`) |
| `APIKeyError` | LLM API 키 인증 실패 |
| `Exception` | 기타 LLM/WebSocket 오류 |

**tool-use 미지원 provider 처리 (pre-fetch):**

RunPod 등 function calling을 지원하지 않는 provider는 1단계 비스트리밍 호출 없이, 토픽 제목과 상대방 마지막 발언을 쿼리로 삼아 검색 결과를 미리 가져온다(`prefetch_evidence`). 검색 결과는 `_build_messages()`에 `prefetch_evidence` 파라미터로 전달되어 시스템 메시지에 삽입된다. 검색 실패 시 경고 로그 후 무시한다 (non-fatal).

---

#### `execute_with_retry()` — 재시도 포함 턴 실행 진입점

```python
async def execute_with_retry(
    match: DebateMatch,
    topic: DebateTopic,
    turn_number: int,
    speaker: str,
    agent: DebateAgent,
    version: DebateAgentVersion | None,
    api_key: str,
    my_claims: list[str],
    opponent_claims: list[str],
    my_accumulated_penalty: int = 0,
    event_meta: dict | None = None,
) -> DebateTurnLog | None
```

**재시도 매트릭스:**

| 예외 유형 | 동작 |
|---|---|
| `APIKeyError` (1회) | 1초 대기 후 1회 재시도 |
| `APIKeyError` (2회 연속) | `MatchVoidError` raise — 매치 무효화 트리거 |
| 그 외 예외 | `debate_turn_max_retries`(기본 2) 횟수까지 재시도 |
| 모든 재시도 소진 | `None` 반환 — 엔진이 `ForfeitError` 처리 |

**재시도 루프 구조:**

```python
for attempt in range(settings.debate_turn_max_retries + 1):
    try:
        return await self.execute(...)
    except APIKeyError:
        if attempt == 0: continue  # 1회 재시도
        raise MatchVoidError(...)
    except Exception:
        if attempt < settings.debate_turn_max_retries: continue
        logger.error(...)
        return None
```

---

## Tool-Use 2단계 파이프라인 (2026-03-23)

`topic.tools_enabled=True`이고 provider가 OpenAI/Anthropic/Google 중 하나일 때 활성화된다.

```
전체 허용 시간: debate_turn_timeout_seconds
│
├─ [1단계] 비스트리밍 비동기 호출 (stage1_timeout = min(전체 × 0.3, 15.0초))
│   │   tool_choice: "auto" (OpenAI/Google) | {"type": "auto"} (Anthropic)
│   │
│   ├─ tool_calls 없음 → 바로 2단계 스트리밍 직행
│   │
│   └─ tool_calls 있음 (web_search 감지)
│       ├─ turn_tool_call SSE 발행 ("근거 검색 중..." 스피너)
│       ├─ EvidenceSearchService.search_by_query(query)
│       ├─ messages에 assistant tool_call + tool result 주입
│       └─ input_tokens / output_tokens 1단계 결과 합산
│
└─ [2단계] 스트리밍 발언 생성 (남은 deadline 시간 내)
    │   tool_used_flag=True 시 tools 파라미터도 전달 (Anthropic 필수)
    └─ turn_chunk SSE 청크별 발행 → full_text 조립
```

### provider별 tool schema 포맷 (`_build_web_search_tool`)

| Provider | 구조 |
|---|---|
| `openai` | `[{"type": "function", "function": {"name": "web_search", ...}}]` |
| `anthropic` | `[{"name": "web_search", "description": ..., "input_schema": {...}}]` |
| `google` | `[{"function_declarations": [{"name": "web_search", ...}]}]` |
| `runpod` / `local` | `[]` (빈 리스트 — tool-use 미지원) |

`settings.debate_tool_use_enabled=False`이면 모든 provider에서 빈 리스트를 반환한다.

---

## `_to_gemini_format()` — Google provider tool 메시지 변환

Google Gemini는 tool result 메시지에 `name` 필드를 `functionResponse.name`으로 요구한다. `messages` 리스트에 주입되는 tool result 딕셔너리에는 `"name": tool_calls[0]["function"]["name"]` 필드가 포함되며, `google_provider.py`의 `_to_gemini_format()`이 이를 읽어 올바른 구조로 변환한다.

---

## turn_tool_call SSE 페이로드

tool call이 감지되었을 때 프론트엔드에 스피너("근거 검색 중...")를 표시하기 위해 발행되는 이벤트.

```json
{
  "turn_number": 3,
  "speaker": "agent_a",
  "tool_name": "web_search",
  "query": "검색 쿼리 문자열"
}
```

`event_meta`가 있는 경우 해당 필드들이 위 필드보다 앞에 병합되지만, `turn_number` / `speaker` / `tool_name` / `query`는 `event_meta` 값으로 덮어쓰여지지 않는다 (`{**(event_meta or {}), "turn_number": ..., ...}` 역순 병합).

---

## 에러 처리

### Redis 장애 시 SSE 발행 실패 (2026-03-24 버그 수정)

`turn_tool_call` SSE 발행(`publish_event`) 호출 전체를 `try/except`로 감싸 Redis 장애 시에도 턴 실행이 중단되지 않는다. 실패 시 `logger.warning`만 기록하고 검색 및 2단계 스트리밍은 정상 계속된다.

`turn_chunk` SSE 발행도 동일 패턴으로 보호되어 있다 (`local` 경로와 스트리밍 경로 모두).

### JSON 파싱 실패 / 토큰 절삭

| 조건 | 처리 |
|---|---|
| `finish_reason == "length"` (max_tokens 초과) | `"claim"` 필드 정규식으로 직접 추출, 실패 시 원문 500자 |
| JSON 파싱 불가 또는 스키마 불일치 | 원문 앞 500자를 claim으로 사용, `raw_response = {"raw": ...}` |
| `finish_reason == "length"` + 정상 파싱 | `raw_response["finish_reason"] = "length"` 메타 추가 |

### 토큰 사용량 기록

`agent.provider != "local"`인 경우 턴 완료 후 `_log_orchestrator_usage(db, agent.owner_id, agent.model_id, input_tokens, output_tokens)`를 호출한다. 1단계 + 2단계 토큰이 합산되어 기록된다.

---

## 관련 설정값 (`config.py`)

| 설정 키 | 기본값 | 설명 |
|---|---|---|
| `debate_turn_timeout_seconds` | 60 | 전체 턴 실행 최대 허용 시간 (초) |
| `debate_turn_max_retries` | 2 | 턴 실패 시 최대 재시도 횟수 |
| `debate_tool_use_enabled` | `True` | web_search tool-use 전체 ON/OFF |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `InferenceClient` | `app.services.llm.inference_client` | LLM 비스트리밍(`generate_byok`) 및 스트리밍(`generate_stream_byok`) 호출 |
| `EvidenceSearchService` | `app.services.debate.evidence_search` | `web_search` 쿼리 실행 및 결과 포맷 |
| `publish_event` | `app.services.debate.broadcast` | SSE 이벤트 (`turn_chunk`, `turn_tool_call`) Redis 발행 |
| `WSConnectionManager` | `app.services.debate.ws_manager` | 로컬 에이전트 WebSocket 턴 요청 |
| `DebateToolExecutor`, `ToolContext`, `AVAILABLE_TOOLS` | `app.services.debate.tool_executor` | 로컬 에이전트 tool call 실행 컨텍스트 |
| `_build_messages`, `validate_response_schema` | `app.services.debate.helpers` | 대화 컨텍스트 구성, LLM 응답 스키마 검증 |
| `MatchVoidError` | `app.services.debate.exceptions` | API 키 2회 실패 시 매치 무효화 신호 |
| `APIKeyError` | `app.services.llm.providers.base` | LLM API 키 인증 실패 예외 |
| `_log_orchestrator_usage` | `app.services.debate.debate_formats` | BYOK 에이전트 토큰 사용량 기록 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.2 | `turn_tool_call` SSE 발행 try/except 보호 추가 — Redis 장애 시 턴 실행 중단 방지 |
| 2026-03-23 | v1.1 | Tool-Use 2단계 파이프라인 추가 (web_search function call 감지 → 증거 주입 → 스트리밍) |
| 2026-03-17 | v1.0 | engine.py 리팩토링(3a715c2)으로 `TurnExecutor` 클래스 분리, 문서 최초 작성 |
