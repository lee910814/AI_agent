# OrchestrationControlPlane

> 토론 실행 정책/컨텍스트를 관리하는 단일 진입점

**파일 경로:** `backend/app/services/debate/control_plane.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

토론 실행 중 의사결정(모델 선택 / 병렬 여부 / 타임아웃 / 재시도)과 추적 메타데이터(trace_id, fallback 이유)를 일관되게 관리한다.

설정값(`OrchestrationPolicy`)과 런타임 상태(`OrchestrationRuntimeContext`)를 명확히 분리하여, 매치 실행 중에 정책이 변경되지 않음을 보장한다.

**점진 롤아웃:** `model_rollout_ratio` 설정으로 신규 모델을 특정 비율의 매치에만 적용할 수 있다. 동일 `match_id`에 대해 SHA-256 해시 기반으로 버킷을 결정하기 때문에 재시작 후에도 동일한 매치는 같은 실험군에 배정된다.

---

## 모듈 레벨 함수: `_stable_bucket(key) -> int`

`key` 문자열을 SHA-256으로 해싱하여 0~9999 범위 정수 버킷으로 변환한다. 동일 입력에 대해 항상 같은 버킷을 반환하므로 재시작 후에도 실험군 배정이 일관된다.

```python
digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
return int(digest[:8], 16) % 10000
```

---

## 데이터 클래스: `OrchestrationPolicy`

```python
@dataclass(frozen=True)
class OrchestrationPolicy:
    mode: str
    review_timeout_seconds: int
    parallel_enabled: bool
    draw_threshold: int
    retry_budget: int
    review_enabled: bool
    review_model: str
    judge_model: str
    review_model_candidate: str    # 롤아웃 대상 신규 모델
    judge_model_candidate: str     # 롤아웃 대상 신규 모델
    model_rollout_ratio: float     # 0.0~1.0
    trace_events_enabled: bool
```

`frozen=True`로 런타임 중 불변성을 보장한다.

### `from_settings() -> OrchestrationPolicy`

`app.core.config.settings`에서 값을 읽어 정책 스냅샷을 생성한다.

- `model_rollout_ratio`는 `min(max(ratio, 0.0), 1.0)`으로 범위를 강제 클램핑한다.
- `review_model` / `judge_model`이 미설정이면 `debate_orchestrator_model` 폴백을 사용한다.

---

## 데이터 클래스: `OrchestrationRuntimeContext`

```python
@dataclass
class OrchestrationRuntimeContext:
    trace_id: str
    match_id: str
    match_format: str
    mode: str                          # "{policy.mode}:{parallel|sequential}"
    started_at: datetime               # UTC 기준 매치 시작 시각
    fallback_counts: dict[str, int]    # "{stage}:{reason}" → 발생 횟수
    transitions: list[dict[str, str]]  # 상태 전이 이력
```

토론 1회 실행 동안 유지된다.

---

## 클래스: `OrchestrationControlPlane`

### `__init__(match_id, match_format, policy, trace_id)`

| 파라미터 | 설명 |
|---|---|
| `match_id` | 매치 UUID 문자열 |
| `match_format` | `'1v1'`, `'2v2'`, `'3v3'` 등 |
| `policy` | `OrchestrationPolicy` (없으면 `from_settings()` 자동 생성) |
| `trace_id` | SSE 페이로드에 붙을 추적 ID (없으면 UUID4 자동 생성) |

`runtime.mode`는 `"{policy.mode}:{parallel|sequential}"` 형태로 설정된다.

---

### `_is_in_rollout(lane) -> bool`

`lane`(`'review'` 또는 `'judge'`)을 포함한 키(`{match_id}:{lane}`)의 버킷이 `model_rollout_ratio * 10000` 미만이면 실험군으로 판정한다.

`model_rollout_ratio <= 0`이면 항상 `False` 반환.

---

### `select_review_model() -> str`

review 단계에 사용할 LLM 모델을 반환한다.

- `review_model_candidate`가 설정되어 있고 해당 매치가 실험군이면 candidate 반환.
- 그 외에는 `review_model` 반환.

---

### `select_judge_model() -> str`

judge 단계에 사용할 LLM 모델을 반환한다. `select_review_model()`과 동일한 롤아웃 로직 적용.

---

### `record_transition(from_status, to_status, reason) -> None`

매치 상태 전이를 `runtime.transitions`에 append한다.

```python
{"from": from_status, "to": to_status, "reason": reason}
```

---

### `mark_fallback(reason, *, stage, turn_number, speaker) -> None`

fallback 발생을 누적 기록하고 WARNING 로그를 남긴다.

`runtime.fallback_counts`의 키는 `"{stage}:{reason}"` 형태이며 호출 시마다 1씩 증가한다.

로그 포맷:

```
Orchestration fallback | trace_id=... match_id=... stage=... reason=... turn=... speaker=...
```

---

### `event_meta(*, turn_number, speaker, fallback_reason) -> dict`

SSE 페이로드에 붙일 공통 메타 dict를 반환한다.

`trace_events_enabled=False`이면 빈 dict를 반환하여 기존 SSE 페이로드와 구조적으로 동일하게 유지한다.

활성화 시 반환 구조:

```json
{
  "trace_id": "...",
  "orchestration_mode": "standard:parallel",
  "turn": 3,
  "speaker": "agent_a",
  "fallback_reason": "..."
}
```

`turn_number`, `speaker`, `fallback_reason`은 전달된 경우에만 포함된다.

---

## 관련 설정값 (`config.py`)

| 설정 키 | 설명 |
|---|---|
| `debate_orchestration_mode` | 오케스트레이션 모드 식별자 (예: `'standard'`) |
| `debate_turn_review_timeout` | 턴 검토 타임아웃 (초) |
| `debate_orchestrator_optimized` | 병렬 실행 활성화 여부 |
| `debate_draw_threshold` | 무승부 판정 점수 임계값 |
| `debate_turn_max_retries` | 턴당 최대 재시도 횟수 |
| `debate_turn_review_enabled` | 턴 검토 활성화 여부 |
| `debate_review_model` | 검토 모델 ID (기본) |
| `debate_judge_model` | 판정 모델 ID (기본) |
| `debate_review_model_candidate` | 검토 모델 롤아웃 후보 |
| `debate_judge_model_candidate` | 판정 모델 롤아웃 후보 |
| `debate_model_rollout_ratio` | 롤아웃 비율 (0.0~1.0) |
| `debate_trace_events_enabled` | SSE 메타 트레이스 활성화 여부 |
| `debate_orchestrator_model` | review/judge 모델 미설정 시 폴백 모델 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `settings` | `app.core.config` | 정책 스냅샷 생성 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.0 | 신규 작성 |
