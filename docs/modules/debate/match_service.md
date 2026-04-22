# match_service.py 모듈 명세

> 매치 조회, 예측투표, 하이라이트, 요약 리포트 관리 서비스

**파일 경로:** `backend/app/services/debate/match_service.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

완료/진행 중 매치 조회, 예측투표 생성·집계·정산, 하이라이트 관리, 요약 리포트 생성을 담당한다. `DebateMatchService`와 `DebateSummaryService` 두 클래스가 같은 파일에 포함되어 있다. `resolve_predictions()` 정산 완료 후 별도 세션으로 `NotificationService.notify_prediction_result()`를 호출한다.

---

## 주요 상수

| 상수 | 설명 |
|---|---|
| `SUMMARY_SYSTEM_PROMPT` | 요약 LLM에 전달하는 시스템 프롬프트. JSON 형식의 `agent_a_arguments`, `agent_b_arguments`, `turning_points`, `overall_summary` 반환 지시 |

---

## 모듈 수준 함수

### `calculate_token_cost(tokens: int, cost_per_1m: Decimal) -> Decimal`

토큰 수와 백만 토큰당 비용으로 실제 비용 산출. `engine.py`도 이 함수를 지연 임포트해 사용한다.

### `_format_summary_log(turns: list, agent_a_name: str, agent_b_name: str) -> str` (내부)

턴 로그를 텍스트로 포맷. 발언 내용(`action`, `claim`, `evidence`)만 포함하고 점수·메타데이터는 제외하여 요약 LLM에 전달한다.

### `_build_rule_violations(turns: list, agent_a_name: str, agent_b_name: str) -> list[str]` (내부)

`DebateTurnLog.review_result`의 `violations` 필드를 `'[에이전트명] 턴N: 위반유형(severity) — 설명'` 형식의 문자열 목록으로 변환한다. `DebateSummaryService.generate_summary()`에서 호출되어 LLM 재해석 없이 직접 `summary_report.rule_violations`에 삽입된다.

### `generate_summary_task(match_id: str) -> None`

백그라운드 태스크 진입점. 앱 공유 `async_session`으로 독립 세션에서 `DebateSummaryService.generate_summary()` 호출.

---

## 클래스: DebateMatchService

### 생성자

```python
def __init__(self, db: AsyncSession)
```

### 메서드

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `get_match` | `(match_id: str) -> dict \| None` | 매치 상세 조회. 에이전트 배치 조회(N+1 방지) + 턴 카운트 포함 |
| `get_match_turns` | `(match_id: str) -> list[DebateTurnLog]` | 턴 로그 전체 (turn_number, speaker ASC) |
| `get_scorecard` | `(match_id: str) -> dict \| None` | 스코어카드 조회. `match.scorecard`가 None이면 None 반환 |
| `list_matches` | `(topic_id, agent_id, status, skip, limit, search, date_from, date_to, include_test) -> tuple[list[dict], int]` | 매치 목록 페이지네이션. 테스트 매치 기본 제외. 에이전트명/토픽 제목 통합 검색. 페이지 내 에이전트 배치 조회로 N+1 방지 |
| `create_prediction` | `(match_id: str, user_id: UUID, prediction: str) -> dict` | 예측투표 생성. `in_progress` 상태 + `debate_prediction_cutoff_turns` 이내만 허용. `IntegrityError`로 동시 중복 삽입 방지 |
| `get_prediction_stats` | `(match_id: str, user_id: UUID) -> dict` | 예측 집계(a_win/b_win/draw/total) + 내 투표 결과(`my_prediction`, `is_correct`) 반환 |
| `resolve_predictions` | `(match_id: str, winner_id: str \| None, agent_a_id: str, agent_b_id: str) -> None` | 판정 후 `is_correct` 일괄 UPDATE. 완료 후 알림 발송 (아래 참조) |
| `get_summary_status` | `(match_id: str) -> dict` | 요약 상태 반환: `unavailable` / `generating` / `ready` |
| `toggle_featured` | `(match_id: str, featured: bool) -> dict` | 하이라이트 설정/해제. 완료 매치만 가능 (관리자 전용) |
| `list_featured` | `(limit: int = 5) -> tuple[list[dict], int]` | 하이라이트 매치 목록 (featured_at DESC). 테스트 매치 제외 |
| `_agent_from_map` | `(agents_map: dict, agent_id) -> dict` | 배치 조회된 `agents_map`에서 에이전트 요약 반환. 삭제된 에이전트는 `"[삭제됨]"` 표시 |

---

## 클래스: DebateSummaryService

### 생성자

```python
def __init__(self, db: AsyncSession)
```

### 메서드

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `generate_summary` | `(match_id: str) -> None` | 매치 완료 후 비동기 호출. 이미 `summary_report`가 있으면 스킵. `debate_summary_model`로 LLM 호출 후 `summary_report` JSONB에 저장. 토큰 사용량 기록 포함 |

---

## SUMMARY_SYSTEM_PROMPT 응답 형식

LLM이 반환하는 JSON 형식 (시스템 프롬프트로 강제):

```json
{
  "agent_a_arguments": ["에이전트A의 핵심 논거 1", "핵심 논거 2"],
  "agent_b_arguments": ["에이전트B의 핵심 논거 1", "핵심 논거 2"],
  "turning_points": ["승부를 가른 결정적 순간 또는 논거 대립 1", "순간 2"],
  "overall_summary": "판정 결과를 포함한 전체 토론 총평 (3-4문장)"
}
```

`turning_points`는 실질적인 승패 갈림 지점이 없으면 빈 배열을 반환한다.

`summary_report` JSONB에 저장되는 최종 구조는 LLM 응답 필드 외에 `rule_violations` (review_result에서 직접 추출), `generated_at`, `model_used`, `input_tokens`, `output_tokens` 필드가 추가된다.

---

## 의존 모듈

| 모듈 | 가져오는 대상 | 용도 |
|---|---|---|
| `app.models.debate_agent` | `DebateAgent` | 에이전트 배치 조회 |
| `app.models.debate_match` | `DebateMatch`, `DebateMatchPrediction` (지연 임포트) | 매치/예측 ORM |
| `app.models.debate_topic` | `DebateTopic` | 토픽 JOIN |
| `app.models.debate_turn_log` | `DebateTurnLog` | 턴 로그 조회 |
| `app.models.llm_model` | `LLMModel` | 요약 모델 조회 |
| `app.models.token_usage_log` | `TokenUsageLog` | 요약 LLM 토큰 기록 |
| `app.core.config` | `settings` | `debate_prediction_cutoff_turns`, `debate_summary_enabled`, `debate_summary_model` |
| `app.core.database` | `async_session` | 알림 훅 및 백그라운드 태스크용 독립 세션 |
| `app.services.llm.inference_client` | `InferenceClient` | 요약 LLM 호출 |
| `app.services.notification_service` | `NotificationService` | 예측 결과 알림 발송 (지연 임포트) |

---

## 호출 흐름

```
API 라우터 (api/debate_matches.py)
  → DebateMatchService.get_match()
  → DebateMatchService.list_matches()
  → DebateMatchService.get_match_turns()
  → DebateMatchService.get_scorecard()
  → DebateMatchService.create_prediction()
  → DebateMatchService.get_prediction_stats()
  → DebateMatchService.get_summary_status()

engine.py (_finalize_match)
  → DebateMatchService.resolve_predictions()
      ├─ DebateMatchPrediction.is_correct 일괄 UPDATE
      ├─ db.commit()
      └─ [알림 — 정산 완료 후]
           async with async_session() as notify_db:
               NotificationService(notify_db).notify_prediction_result(match_id)
               notify_db.commit()
           (실패 시 warning 로그 후 계속 진행)
  → asyncio.create_task(generate_summary_task(match_id))

API 라우터 (api/admin/debate/matches.py)
  → DebateMatchService.toggle_featured()
  → DebateMatchService.list_featured()
```

### resolve_predictions() 상세 흐름

```
resolve_predictions(match_id, winner_id, agent_a_id, agent_b_id)
  1. winner_id 기준으로 correct_pred 결정
     ├─ winner_id == None → "draw"
     ├─ winner_id == agent_a_id → "a_win"
     └─ 나머지 → "b_win"
  2. DebateMatchPrediction UPDATE
     WHERE match_id = match_id
     SET is_correct = (prediction == correct_pred)
  3. db.commit()
  4. 알림 발송 (핵심 경로 커밋 완료 후 별도 세션)
     async with async_session() as notify_db:
         NotificationService(notify_db).notify_prediction_result(match_id)
         notify_db.commit()
     (Exception → warning 로그, 정산 결과에 영향 없음)
```

---

## 에러 처리

| 상황 | 예외 | HTTP 상태 |
|---|---|---|
| 매치 미존재 | `ValueError("Match not found")` | 404 |
| 진행 중이 아닌 매치에 예측 | `ValueError("투표는 진행 중인 매치에서만 가능합니다")` | 400 |
| 예측 기한 초과 | `ValueError("투표 시간이 지났습니다 ({N}턴 이후 불가)")` | 400 |
| 중복 예측 (정상 경로) | `ValueError("이미 예측에 참여했습니다")` | 409 |
| 중복 예측 (동시 요청) | `IntegrityError` → 롤백 후 `ValueError` | 409 |
| 미완료 매치 하이라이트 설정 | `ValueError("완료된 매치만 하이라이트로 설정 가능합니다")` | 400 |
| 요약 모델 미등록 | 로그 warning 후 `generate_summary()` 조기 return | — |
| 요약 LLM 호출 실패 | `Exception` → 로그 warning 후 계속 진행 | — |
| 알림 발송 실패 | `Exception` → 로그 warning 후 계속 진행 | — |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-24 | v2.2 | `SUMMARY_SYSTEM_PROMPT` 응답 형식 수정 (`key_arguments`/`winning_points` → `agent_a_arguments`/`agent_b_arguments`/`turning_points`). `_build_rule_violations()` 내부 함수 추가. `_format_summary_log()` 설명 정확화. `summary_report` JSONB 최종 저장 구조 명시 | Claude |
| 2026-03-12 | v2.1 | resolve_predictions() 알림 훅 흐름 명시, NotificationService 의존 모듈 추가, 에러 처리 표 보강 | Claude |
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
