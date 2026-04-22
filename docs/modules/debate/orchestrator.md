# DebateOrchestrator

> 턴별 LLM 발언 검토 담당 오케스트레이터

**파일 경로:** `backend/app/services/debate/orchestrator.py`
**최종 수정일:** 2026-03-17

---

## 모듈 목적

매 턴마다 경량 LLM(`debate_review_model`, 기본: `gpt-4o-mini`)으로 에이전트 발언을 검토하여 논리 점수·위반 감지·벌점 산출·차단 여부를 반환한다.

> **역할 분리 주의:** 최종 판정(judge)과 ELO 계산 역할은 각각 `judge.py`의 `DebateJudge`와 `helpers.py`의 `calculate_elo()`로 분리됨. orchestrator.py는 **턴 검토(review_turn)만** 담당한다.

---

## 주요 상수

| 상수 | 설명 |
|---|---|
| `PENALTY_KO_LABELS` | 벌점 키 → 한국어 라벨 매핑. `false_source`(코드 기반)와 LLM 탐지 7종(Tool-Use 포함) |
| `LLM_VIOLATION_PENALTIES` | 위반 유형 → 벌점 매핑 (7종, Tool-Use 2종 포함) |
| `REVIEW_SYSTEM_PROMPT` | Review LLM 시스템 프롬프트. logic_score/violations/feedback/block 포함 JSON 응답 강제. XML 구분자 안내 포함 (2026-03-24) |

### LLM_VIOLATION_PENALTIES (현행)

```python
LLM_VIOLATION_PENALTIES: dict[str, int] = {
    "prompt_injection": 10,  # 시스템 지시 무력화
    "ad_hominem": 8,         # 인신공격
    "false_citation": 8,     # 허위 출처 인용 (Tool-Use 활성 시 — 2026-03-23)
    "straw_man": 6,          # 상대 주장 왜곡·과장
    "off_topic": 5,          # 주제 이탈
    "repetition": 3,         # 의미적 반복
    "no_web_evidence": 3,    # 웹 검색 가능한데 근거 미제시 (Tool-Use 활성 시 — 2026-03-23)
}
```

> `no_web_evidence`, `false_citation`은 `DEBATE_TOOL_USE_ENABLED=true`일 때 `REVIEW_SYSTEM_PROMPT`에 조건부 주입되는 위반 유형이다. Tool-Use 비활성 상태에서는 검토 대상이 아니다.

> 구버전에 있던 `false_claim`, `hasty_generalization`, `genetic_fallacy`, `appeal`, `slippery_slope`, `circular_reasoning`, `accent`, `division`, `composition` 등은 제거됨.

### PENALTY_KO_LABELS (현행)

| 키 | 한국어 라벨 | 탐지 경로 |
|---|---|---|
| `false_source` | 허위 출처 | turn_executor.py 코드 기반 |
| `prompt_injection` | 프롬프트 인젝션(LLM) | review_turn() |
| `ad_hominem` | 인신공격(LLM) | review_turn() |
| `false_citation` | 허위 출처 인용(LLM) | review_turn() — Tool-Use 활성 시 |
| `straw_man` | 허수아비 논증(LLM) | review_turn() |
| `off_topic` | 주제 이탈(LLM) | review_turn() |
| `repetition` | 주장 반복(LLM) | review_turn() |
| `no_web_evidence` | 근거 미제시(LLM) | review_turn() — Tool-Use 활성 시 |
| `llm_no_web_evidence` | 근거 미제시(LLM) | review_turn() — `llm_` 접두사 경로 |
| `llm_false_citation` | 허위 출처 인용(LLM) | review_turn() — `llm_` 접두사 경로 |

---

## 클래스: DebateOrchestrator

### 생성자

```python
def __init__(self, optimized: bool = True, client: InferenceClient | None = None) -> None
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `optimized` | `bool` | `True`: `debate_review_model` 사용. `False`: `debate_turn_review_model` 또는 기본 모델 사용 |
| `client` | `InferenceClient \| None` | 외부 주입 시 커넥션 풀 재사용. `None`이면 내부에서 새로 생성하고 소유권 보유 |

`engine.py`의 `DebateEngine._run_with_client()`에서 공유 `InferenceClient`를 주입해 인스턴스화한다.

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `aclose` | `() -> None` | 자신이 소유(`_owns_client=True`)한 클라이언트만 닫기 |
| `review_turn` | `(topic, speaker, turn_number, claim, evidence, action, opponent_last_claim?, recent_history?) -> dict` | 단일 턴 LLM 품질 검토. 실패 시 폴백 반환 |
| `_call_review_llm` | `(model_id, api_key, messages) -> tuple[ReviewResult, int, int]` | LLM 호출 → 마크다운 제거 → Pydantic 파싱 → `(review, input_tokens, output_tokens)` 반환 |
| `_build_review_result` | `(review, input_tokens, output_tokens, skipped?, model_id?) -> dict` | ReviewResult를 최종 결과 dict로 변환 |
| `_review_fallback` | `() -> dict` | 검토 실패 시 안전 폴백 반환 (`logic_score=5`, 위반 없음, `block=False`) |

### `review_turn` 파라미터

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `topic` | `str` | 토론 주제 제목 |
| `speaker` | `str` | 발언자 레이블 (예: `agent_a`, `agent_b_slot0`) |
| `turn_number` | `int` | 현재 턴 번호 |
| `claim` | `str` | 에이전트 주요 주장 |
| `evidence` | `str \| None` | 근거/데이터 (없으면 None) |
| `action` | `str` | 발언 타입 (argue/rebut/concede/question/summarize) |
| `opponent_last_claim` | `str \| None` | 직전 상대 발언 (있으면 포함) |
| `recent_history` | `list[str] \| None` | 최근 2턴 발언 목록 (순환논증·패턴 탐지용) |

### `review_turn` 반환 dict 구조

```python
{
    "logic_score": int,           # 1-10, LLM 평가 논리 점수
    "violations": list[dict],     # [{"type": str, "severity": "minor|severe", "detail": str}, ...]
    "feedback": str,              # 관전자용 한줄평 (30자 이내, 한국어)
    "block": bool,                # True이면 원문 차단 → blocked_claim으로 교체
    "penalties": dict[str, int],  # 위반 유형 → 벌점 (LLM_VIOLATION_PENALTIES 기반)
    "penalty_total": int,         # 벌점 합계
    "blocked_claim": str | None,  # block=True이면 "[차단됨: 규칙 위반으로 발언이 차단되었습니다]"
    "input_tokens": int,
    "output_tokens": int,
    "model_id": str,
    # optimized=True 모드에서만 포함:
    "skipped": bool,              # False = 검토 수행됨
}
```

---

## 모델 선택 로직

```python
if self.optimized:
    model_id = settings.debate_review_model or settings.debate_orchestrator_model
else:
    # DEBATE_ORCHESTRATOR_OPTIMIZED=false 롤백 경로
    model_id = settings.debate_turn_review_model or settings.debate_orchestrator_model
```

---

## Pydantic 스키마 강제 (OpenAI 전용)

OpenAI provider 사용 시 `response_format`에 `json_schema`를 지정하여 API 레벨에서 출력 형식을 강제한다.

```python
if provider == "openai":
    kwargs["response_format"] = {
        "type": "json_schema",
        "json_schema": {"name": "review_result", "schema": ReviewResult.model_json_schema()},
    }
```

---

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| API 키 미설정 | 즉시 `_review_fallback()` 반환 (LLM 호출 없음) |
| `debate_turn_review_timeout` 초과 | `TimeoutError` 포착 → `_review_fallback()` 반환. 토론 진행 중단 없음 |
| JSON 파싱 실패 | `json.JSONDecodeError` / `ValidationError` 포착 → `_review_fallback()` 반환 |
| 네트워크·API 장애 | `Exception` 포착 → `_review_fallback()` 반환 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `settings` | `app.core.config` | 모델 ID, 타임아웃, 토큰 상한 읽기 |
| `InferenceClient` | `app.services.llm.inference_client` | LLM API 호출 (`generate_byok`) |

### 관련 설정값 (`config.py`)

| 설정 키 | 설명 |
|---|---|
| `debate_review_model` | 턴 검토 경량 모델 (`optimized=True`일 때) |
| `debate_turn_review_model` | 턴 검토 모델 (`optimized=False` 롤백 경로) |
| `debate_orchestrator_model` | 폴백 기본 모델 |
| `debate_orchestrator_optimized` | 병렬 실행 + 모델 분리 활성화 |
| `debate_turn_review_enabled` | LLM 검토 전체 활성화 여부 |
| `debate_turn_review_timeout` | `review_turn` LLM 호출 타임아웃 (초) |
| `debate_review_max_tokens` | review LLM 최대 출력 토큰 |

---

## 호출 흐름 (병렬 실행 모드)

```
debate_formats.py (_run_parallel_turns)
  → asyncio.create_task(
      orchestrator.review_turn(turn_a),   # A 검토 백그라운드 시작
    )
  → executor.execute_with_retry(agent_b)  # B 실행 (병렬)
  → await review_a_task                   # A 검토 결과 수집 (B 실행 중 진행)
  → _apply_review_to_turn(turn_a, review_a, ...)
  → prev_b_review_task = asyncio.create_task(
      orchestrator.review_turn(turn_b),   # B 검토 백그라운드 시작 (다음 턴에 수집)
    )
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | Tool-Use 위반 유형 2종 추가(`no_web_evidence`, `false_citation`); `REVIEW_SYSTEM_PROMPT`에 XML 구분자 안내 추가 (prompt injection 방어); `review_turn` user_content XML 태그로 에이전트 발언 격리 |
| 2026-03-23 | Tool-Use 연동 — `no_web_evidence`/`false_citation` 벌점, `tools_available` 조건부 규칙 주입 |
| 2026-03-17 | 현행 코드 기반 전면 재작성. judge/ELO 역할 분리 명시, 위반 유형 현행 5종으로 정정, `calculate_elo` re-export 및 2-stage 판정 내용 judge.md로 이동 |
| 2026-03-12 | 위반 유형 확장, 규칙 준수 재작성 |
