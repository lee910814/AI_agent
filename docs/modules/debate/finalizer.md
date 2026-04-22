# MatchFinalizer

> 매치 완료 후처리 통합 클래스

**파일 경로:** `backend/app/services/debate/finalizer.py`
**최종 수정일:** 2026-03-17

---

## 모듈 목적

`DebateJudge.judge()`가 반환한 판정 결과를 받아 ELO 갱신·시즌·승급전·DB 커밋·SSE 발행·예측투표·토너먼트·요약 리포트까지 매치 완료에 필요한 모든 후처리를 순서대로 실행한다.

1v1과 멀티에이전트 포맷의 공통 진입점.

---

## 클래스: MatchFinalizer

### 생성자

```python
def __init__(self, db: AsyncSession) -> None
```

---

## `finalize(match, judgment, agent_a, agent_b, model_cache, usage_batch)`

### 파라미터

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `match` | `DebateMatch` | 완료 처리할 매치 |
| `judgment` | `dict` | `DebateJudge.judge()`의 반환값 |
| `agent_a` | `DebateAgent` | A측 에이전트 |
| `agent_b` | `DebateAgent` | B측 에이전트 |
| `model_cache` | `dict` | LLMModel 캐시 (토큰 비용 계산용) |
| `usage_batch` | `list[TokenUsageLog]` | 일괄 INSERT용 토큰 로그 목록 |

### 처리 순서

```
1. Judge 토큰 usage_batch 추가
   → _log_orchestrator_usage(judge 모델, input_tokens, output_tokens)

2. ELO 계산
   → elo_result = "a_win" | "b_win" | "draw"
   → calculate_elo(elo_a_before, elo_b_before, elo_result, score_diff)

3. match 필드 갱신
   → scorecard, score_a, score_b, winner_id, status="completed", finished_at

4. 누적 ELO 갱신 (is_test=False 시)
   → agent_service.update_elo(agent_a, new_a, result_a, version_a_id)
   → agent_service.update_elo(agent_b, new_b, result_b, version_b_id)

5. 시즌 ELO 갱신 (match.season_id 있을 때만)
   → _update_season_elo(match, agent_a, agent_b, elo_result, ...)

6. 승급전/강등전 결과 반영 (is_test=False 시)
   → DebatePromotionService.get_active_series(agent_id)
   → DebatePromotionService.record_match_result(series_id, result)
   → 시리즈 완료 시 → promo_svc.check_and_trigger(새 시리즈 가능성 확인)
   → series_update SSE 발행

7. DB 커밋 + usage_batch 일괄 INSERT
   → UPDATE DebateMatch SET elo_a_before/after, elo_b_before/after
   → db.add_all(usage_batch)
   → db.commit()

8. finished SSE 발행 (커밋 후 발행 — 새로고침 시 DB 결과와 일치 보장)
   → try/except로 보호: SSE 실패 시에도 match.status를 'error'로 덮어쓰지 않음
   → publish_event(match_id, "finished", {winner_id, score_a, score_b, elo_*})

9. 예측투표 정산
   → DebateMatchService.resolve_predictions(match_id, winner_id, agent_a_id, agent_b_id)

10. 토너먼트 라운드 진행 (match.tournament_id 있을 때만)
    → DebateTournamentService.advance_round(tournament_id)

11. 요약 리포트 백그라운드 태스크 (debate_summary_enabled=True 시)
    → asyncio.create_task(generate_summary_task(match_id))
```

### 설계 원칙

- **커밋 전 SSE 발행 금지:** finished SSE는 반드시 DB 커밋 완료 후 발행. 새로고침 시 DB와 SSE 결과가 불일치하는 버그 방지.
- **SSE 예외 격리 (CRITICAL, 2026-03-24):** `finished` SSE와 `series_update` SSE는 각각 try/except로 감쌓다. DB commit(step 7) 이후 SSE 발행 실패가 `run_debate()` except Exception까지 전파되면, 이미 'completed'로 커밋된 `match.status`가 'error'로 덮어씌워지는 치명적 버그가 있었다. try/except로 격리하여 SSE 실패가 완료 상태에 영향을 주지 않는다.
- **is_test 플래그:** `match.is_test=True`이면 ELO·시즌·승급전 처리를 건너뜀.
- **순환 import 방지:** `agent_service`, `match_service`, `promotion_service`, `tournament_service`는 함수 레벨에서 import.

---

## finished SSE 페이로드

```json
{
  "winner_id": "uuid | null",
  "score_a": 65,
  "score_b": 58,
  "elo_a_before": 1200,
  "elo_a_after": 1218,
  "elo_b_before": 1185,
  "elo_b_after": 1167,
  "elo_a": 1218,
  "elo_b": 1167
}
```

> `elo_a`, `elo_b`는 `elo_a_after`, `elo_b_after`와 동일. 하위 호환 목적으로 함께 포함.

---

## 시리즈 완료 후 재트리거 로직

```python
if series_result.get("status") in ("won", "lost", "expired"):
    # 시리즈 완료 후 같은 매치 ELO로 새 시리즈 트리거 가능성 확인 (최대 1회)
    new_series = await promo_svc.check_and_trigger(
        agent_id, 0, elo_after, post_tier, post_protection
    )
    if new_series:
        series_updates.append({...새 시리즈 정보...})
```

승급전 승리로 티어가 바뀐 직후 다음 승급전 가능 조건을 즉시 확인해 연속 트리거를 허용한다 (최대 1회).

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `DebateAgentService` | `app.services.debate.agent_service` | ELO 갱신, 전적 업데이트 |
| `DebateMatchService` | `app.services.debate.match_service` | 예측투표 정산, 요약 태스크 |
| `DebatePromotionService` | `app.services.debate.promotion_service` | 승급전/강등전 결과 반영 |
| `DebateTournamentService` | `app.services.debate.tournament_service` | 토너먼트 라운드 진행 |
| `publish_event` | `app.services.debate.broadcast` | SSE 이벤트 발행 |
| `calculate_elo` | `app.services.debate.helpers` | ELO 계산 |
| `_update_season_elo` | `app.services.debate.forfeit` | 시즌 ELO 갱신 |
| `_log_orchestrator_usage` | `app.services.debate.debate_formats` | 토큰 사용량 기록 |
| `settings` | `app.core.config` | `debate_summary_enabled` 확인 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.1 | `finished` SSE + `series_update` SSE try/except 보호 추가 (CRITICAL 버그 수정 — DB 커밋 후 SSE 실패 시 match.status 'error' 덮어쓰기 방지) |
| 2026-03-17 | v1.0 | 신규 작성. finalizer.py 분리 반영. 처리 순서, finished SSE 페이로드, 시리즈 재트리거 로직 문서화 |
