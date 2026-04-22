# DebateFormats

> 포맷별 턴 루프 함수 모음 및 포맷 dispatch 레이어

**파일 경로:** `backend/app/services/debate/debate_formats.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

`DebateEngine._run_with_client()`가 매치 포맷(`"1v1"` / `"2v2"` / `"3v3"`)을 판단한 뒤 `get_format_runner()`로 적합한 턴 루프 함수를 선택한다. 각 턴 루프 함수는 에이전트 발언 실행(TurnExecutor), LLM 검토(DebateOrchestrator), SSE 이벤트 발행(broadcast), 토큰 사용량 기록을 모두 포함하며, 실행 결과를 `TurnLoopResult`로 반환해 `DebateEngine`에 전달한다.

---

## 데이터 클래스: `TurnLoopResult`

턴 루프 종료 후 `DebateEngine`에 반환하는 집계 결과.

```python
@dataclass
class TurnLoopResult:
    claims_a: list[str]        # A측 발언 목록 (차단된 경우 blocked_claim 텍스트로 대체)
    claims_b: list[str]        # B측 발언 목록 (차단된 경우 blocked_claim 텍스트로 대체)
    total_penalty_a: int       # A측 누적 벌점 합계
    total_penalty_b: int       # B측 누적 벌점 합계
    model_cache: dict          # LLMModel 캐시 (model_id → LLMModel), finalizer에 전달
    usage_batch: list          # 커밋 전 모아둔 TokenUsageLog 목록, finalizer에서 일괄 INSERT
```

`claims_*`는 판정(judge) 단계의 입력이 된다. 차단된 발언은 원문이 아닌 `blocked_claim` 텍스트로 교체돼 판정 모델에 전달된다.

---

## `get_format_runner(match_format)`

매치 포맷에 대응하는 턴 루프 함수를 반환하는 dispatch 함수.

```python
_FORMAT_RUNNERS: dict[str, Callable] = {
    "1v1": run_turns_1v1,
    "2v2": run_turns_multi,
    "3v3": run_turns_multi,
}

def get_format_runner(match_format: str) -> Callable:
    return _FORMAT_RUNNERS.get(match_format, run_turns_1v1)
```

**폴백:** 등록되지 않은 포맷은 `run_turns_1v1`으로 폴백한다.

**신규 포맷 추가 방법:** 턴 루프 함수 1개를 작성하고 `_FORMAT_RUNNERS`에 1줄 추가하면 된다.

---

## `run_turns_1v1()`

1v1 포맷 턴 루프의 진입점. `parallel` 플래그에 따라 내부 구현을 선택한다.

### 시그니처

```python
async def run_turns_1v1(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match: DebateMatch,
    topic: DebateTopic,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    version_a: DebateAgentVersion | None,
    version_b: DebateAgentVersion | None,
    api_key_a: str,
    api_key_b: str,
    model_cache: dict,
    usage_batch: list,
    parallel: bool,
    control_plane: OrchestrationControlPlane | None = None,
) -> TurnLoopResult
```

### 실행 분기

| `parallel` 값 | 호출 함수 | 비고 |
|---|---|---|
| `True` | `_run_parallel_turns()` | `DEBATE_ORCHESTRATOR_OPTIMIZED=true` 시 |
| `False` | `_run_sequential_turns()` | 롤백 경로, 기본값 |

### 예외

- `ForfeitError`: 에이전트 발언이 재시도를 모두 소진한 경우 raise.

---

## 롤링 병렬 패턴 (`_run_parallel_turns`)

`DEBATE_ORCHESTRATOR_OPTIMIZED=true` 시 적용되는 병렬 실행 패턴. 전체 턴 지연을 약 37% 단축한다.

### 핵심 원리

각 턴에서 **A 검토**와 **B 실행**을 `asyncio.create_task`로 동시에 진행한다. B가 발언하는 시간 동안 A 검토가 백그라운드에서 완료되므로 LLM 검토 대기시간이 숨겨진다.

```
턴 N:
  ┌──────────────────────────────────────────────────┐
  │  A 실행 (await)                                   │
  ├──────────────────────────────────────────────────┤
  │  [이전 턴 B 리뷰 수집 (await prev_b_review_task)] │
  │  → A 실행 (await)                                │
  │  → A 리뷰 Task 생성 (백그라운드 시작)             │
  │  → A 근거 검색 Task 생성 (백그라운드 시작)         │
  │  → B 실행 (await) ← 이 시간 동안 A 리뷰 진행 중  │
  │  → B 리뷰 Task 생성 (백그라운드 시작)             │
  │  → A 리뷰 결과 수집 (await review_a_task)        │
  └──────────────────────────────────────────────────┘
턴 N+1:
  → [B 리뷰 수집 (await prev_b_review_task)] ...
```

### 롤링 루프의 상태 변수

| 변수 | 설명 |
|---|---|
| `prev_b_review_task` | 이전 턴 B 리뷰 Task. 다음 턴 A 실행 직전에 `await` |
| `prev_b_evidence_task` | 이전 턴 B 근거 검색 Task |
| `prev_turn_b` | 이전 턴 B의 `DebateTurnLog` 참조 (리뷰 결과 반영용) |
| `prev_b_turn_num` | 이전 턴 번호 (SSE 이벤트 발행용) |

### 루프 종료 후 마지막 B 리뷰 처리 (end-of-loop)

루프 마지막 턴의 B 리뷰 Task는 루프 밖에서 별도로 수집한다.

```python
# 2026-03-24 버그 수정: review_task를 먼저 await 후 evidence_task.done() 체크
# LLM 호출(수백 ms) 완료 시점에 evidence_task도 done()일 가능성이 높아지는 순서
if settings.debate_turn_review_enabled and prev_b_review_task is not None:
    review_last_b = await prev_b_review_task  # ① 먼저 review 수집
    ...
if prev_b_evidence_task is not None and prev_turn_b is not None:
    if prev_b_evidence_task.done() and not prev_b_evidence_task.cancelled():
        evidence_last_b = prev_b_evidence_task.result()  # ② 이미 완료된 경우만 처리
    else:
        prev_b_evidence_task.cancel()  # ③ 미완료 태스크는 취소 (고아 방지)
```

이전 구현에서는 `prev_b_evidence_task.done()` 체크를 `prev_b_review_task` await보다 먼저 수행했기 때문에, LLM 리뷰가 완료되기 전에 evidence 태스크를 조기 취소하는 경우가 있었다. 수정 후에는 review await가 수백 ms 소요되는 사이 evidence 태스크도 완료될 가능성이 높아졌다.

### ForfeitError 시 태스크 정리

발언 실패(`execute_with_retry` → `None`) 시 실행 중인 백그라운드 태스크를 모두 취소한다.

```python
if turn_b is None:
    for _t in [review_a_task, evidence_a_task, prev_b_review_task, prev_b_evidence_task]:
        if _t and not _t.done():
            _t.cancel()
    raise ForfeitError(forfeited_speaker="agent_b")
```

---

## Tool-Use 가드 (post-hoc evidence 덮어쓰기 방지)

`EvidenceSearchService`가 사후(post-hoc)로 근거를 검색해 `turn.evidence`에 패치하지만, 에이전트가 `web_search` 도구를 직접 사용한 경우에는 이미 정확한 근거가 확보돼 있으므로 덮어쓰지 않는다.

```python
# tool_used == "web_search"이면 사후 evidence 패치 생략
raw = turn_a.raw_response or {}
if isinstance(evidence_a, EvidenceResult) and raw.get("tool_used") != "web_search":
    turn_a.evidence = evidence_a.format()
    used_sources.update(evidence_a.sources)
    ...
```

`_TOOL_USE_PROVIDERS`는 모듈 상수로 선언돼 있다.

```python
_TOOL_USE_PROVIDERS = frozenset({"openai", "anthropic", "google"})
```

Tool-Use 활성화 조건:

```python
tools_available = (
    settings.debate_tool_use_enabled
    and topic.tools_enabled
    and agent.provider in _TOOL_USE_PROVIDERS
)
```

---

## 출처 중복 방지 (`used_sources`)

매치 단위로 `used_sources: set[str]`를 유지한다. 동일 URL이 여러 턴에 걸쳐 반복 인용되지 않도록 `EvidenceSearchService.search()`에 `exclude_urls`로 전달한다.

```python
used_sources: set[str] = set()
...
_evidence_service.search(turn_a.claim, exclude_urls=set(used_sources))
...
used_sources.update(evidence_a.sources)
```

---

## 순차 실행 패턴 (`_run_sequential_turns`)

`DEBATE_ORCHESTRATOR_OPTIMIZED=false` 또는 롤백 경로에서 사용. 처리 순서가 단순하고 예측 가능하다.

### 처리 순서 (턴당)

```
A 실행 → A 검토 (await) → A 이벤트 발행
→ 딜레이 (검토 소요시간 차감)
→ B 실행 → B 검토 (await) → B 이벤트 발행
→ 딜레이 (마지막 턴 제외)
```

### 관전 UX 보존

검토 소요시간을 딜레이에서 차감해 관전자가 인지하는 실제 턴 간격을 일정하게 유지한다.

```python
# 관전 UX: 딜레이에서 검토 소요시간 차감
remaining_delay = settings.debate_turn_delay_seconds - review_elapsed
if remaining_delay > 0:
    await asyncio.sleep(remaining_delay)
```

### 순차 모드의 `_apply_review_to_turn` 차이점

순차 모드(`update_last_claim=False`)는 검토 완료 후 발언을 `claims`에 추가한다. 차단 시에도 인덱스 보존을 위해 `blocked_claim` 텍스트를 append한다.

```python
# 병렬 모드: update_last_claim=True (이미 append된 마지막 항목을 패치)
# 순차 모드: update_last_claim=False (검토 후 append)
```

---

## `run_turns_multi()`

2v2/3v3 멀티에이전트 포맷 턴 루프. 라운드 로빈 방식으로 각 팀의 슬롯을 순환 실행한다.

### 구조

```
participants 조회 (team A/B 분류)
  → agents/versions 배치 조회 (루프 진입 전 1회)
  → for turn_num in range(1, max_turns + 1):
      → for i in range(max_slots):
          → a_part = team_a[i % len(team_a)]   # 팀 간 슬롯 수 불일치 시 mod 순환
          → b_part = team_b[i % len(team_b)]
          → _run_multi_slot_turn(... "agent_a", f"agent_a_slot{i}" ...)
          → _run_multi_slot_turn(... "agent_b", f"agent_b_slot{i}" ...)
```

### 슬롯 레이블

프론트엔드 멀티에이전트 구분을 위해 `speaker` 필드에 슬롯 인덱스를 포함한 레이블을 사용한다.

| 필드 | 값 예시 |
|---|---|
| `turn.speaker` (DB) | `"agent_a"` / `"agent_b"` (1v1과 동일) |
| `turn_slot` SSE 이벤트 `speaker` | `"agent_a_slot0"`, `"agent_a_slot1"`, ... |

### `_run_multi_slot_turn()` 내부 처리

중복 코드 제거를 위해 추출된 헬퍼 함수. 단일 슬롯에 대해 실행 → 검토 → 이벤트 발행을 순차 처리한다.

```python
async def _run_multi_slot_turn(
    ...,
    speaker_role: str,    # "agent_a" | "agent_b" (DB 저장 및 TurnExecutor용)
    speaker_label: str,   # "agent_a_slot0" 등 (SSE 이벤트 식별용)
    ...
) -> int  # 반환: 업데이트된 total_penalty
```

멀티 포맷은 병렬 실행을 지원하지 않는다. 모든 슬롯이 순차적으로 실행된다.

---

## 내부 헬퍼 함수

| 함수 | 역할 |
|---|---|
| `_publish_turn_event()` | 턴 완료 SSE 이벤트 발행 (`"turn"` 타입) |
| `_publish_review_event()` | 리뷰 결과 SSE 이벤트 발행 (`"turn_review"` 타입) |
| `_apply_review_to_turn()` | 리뷰 결과를 `DebateTurnLog`에 반영, 누적 벌점 반환 |
| `_log_orchestrator_usage()` | 오케스트레이터 LLM 호출 토큰을 `token_usage_logs`에 기록 |

### `_log_orchestrator_usage()` 동작 방식

- `input_tokens == 0 and output_tokens == 0`이면 즉시 반환 (폴백/스킵된 호출).
- `model_cache`를 활용해 동일 모델의 반복 DB `SELECT`를 방지한다.
- `usage_batch`가 `None`이면 즉시 `db.add()`, 있으면 배치에 추가해 매치 종료 시 일괄 `INSERT`.

### `_apply_review_to_turn()` 모드별 차이

| 모드 | `update_last_claim` | 동작 |
|---|---|---|
| 병렬 (parallel) | `True` | 이미 append된 `claims[-1]`을 차단본으로 패치 |
| 순차 (sequential) | `False` | 검토 완료 후 `claims.append()` — 차단 시 `blocked_claim` 텍스트 append |

---

## 관련 설정값 (`config.py`)

| 설정 키 | 설명 |
|---|---|
| `debate_orchestrator_optimized` | `True` → `parallel=True` (롤링 병렬 패턴 활성화) |
| `debate_turn_review_enabled` | `True` → 매 발언마다 LLM 검토 실행 |
| `debate_turn_delay_seconds` | 턴 간 딜레이 (초). 검토 소요시간 차감 후 적용 |
| `debate_evidence_search_enabled` | `True` → 사후 근거 검색 Task 생성 |
| `debate_tool_use_enabled` | `True` → Tool-Use 활성화 (provider 지원 여부와 AND 조건) |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `TurnExecutor` | `app.services.debate.turn_executor` | 단일 턴 실행 (재시도 포함) |
| `DebateOrchestrator` | `app.services.debate.orchestrator` | LLM 검토, 폴백 결과 제공 |
| `EvidenceSearchService` | `app.services.debate.evidence_search` | 사후 근거 검색 |
| `publish_event` | `app.services.debate.broadcast` | SSE 이벤트 발행 |
| `_resolve_api_key` | `app.services.debate.helpers` | API 키 해결 (멀티에이전트) |
| `ForfeitError` | `app.services.debate.forfeit` | 몰수패 예외 |
| `OrchestrationControlPlane` | `app.services.debate.control_plane` | 트레이싱·폴백 마킹 (TYPE_CHECKING) |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.0 | 신규 작성. 코드 직접 분석 기반 — TurnLoopResult, get_format_runner, 롤링 병렬/순차 패턴, Tool-Use 가드, 멀티에이전트 포맷 문서화 |
| 2026-03-24 | — | 버그 수정 반영: end-of-loop에서 `prev_b_review_task` await를 `prev_b_evidence_task.done()` 체크 앞으로 이동 |
