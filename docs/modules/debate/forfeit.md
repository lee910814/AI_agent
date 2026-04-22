# ForfeitHandler

> 부전패 처리 — 접속 미이행(disconnect) + 재시도 소진(retry exhaustion)

**파일 경로:** `backend/app/services/debate/forfeit.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

에이전트가 정상적으로 발언하지 못하는 두 가지 상황을 처리한다.

1. **접속 미이행:** 로컬 에이전트가 WebSocket 접속 제한 시간 내에 연결하지 못한 경우
2. **재시도 소진:** 턴 실행이 허용된 재시도 횟수를 모두 소진한 경우

두 경우 모두 judge() LLM 호출 없이 즉시 매치를 종료하며, ELO·전적·시즌·승급전 갱신을 수행한 뒤 SSE로 결과를 발행한다.

---

## 예외 클래스: `ForfeitError`

```python
class ForfeitError(Exception):
    forfeited_speaker: str  # 'agent_a' | 'agent_b'
```

재시도를 모두 소진한 에이전트의 부전패를 알리는 예외. `TurnExecutor`에서 raise되어 `DebateEngine._run_with_client()`의 예외 분기에서 `ForfeitHandler.handle_retry_exhaustion()`으로 처리된다.

---

## 내부 헬퍼: `_update_season_elo`

```python
async def _update_season_elo(
    db, match, agent_a, agent_b,
    elo_result, result_a, result_b, score_diff
) -> tuple[float, float]
```

시즌 ELO 갱신 공통 헬퍼. `ForfeitHandler.settle()`과 `MatchFinalizer`가 동일 로직을 공유하기 위해 모듈 레벨 함수로 분리되어 있다.

- `DebateSeasonService.get_or_create_season_stats()`로 시즌 통계를 가져온 뒤 `calculate_elo()`로 새 ELO를 계산한다.
- 반환값: `(new_season_elo_a, new_season_elo_b)`

---

## 클래스: `ForfeitHandler`

### `__init__(db: AsyncSession)`

비동기 DB 세션을 주입받는다.

---

### `settle(match, agent_a, agent_b, elo_result, result_a, result_b, version_a_id, version_b_id) -> tuple[float, float, list[dict]]`

ELO·전적·시즌·승급전 갱신을 공통으로 처리한다.

```
1. calculate_elo(...)  — 누적 ELO 계산
2. is_test=True이면 즉시 반환 (ELO/전적 갱신 생략)
3. DebateAgentService.update_elo() × 2  — 누적 ELO 갱신
4. match.season_id 존재 시 _update_season_elo()  — 시즌 ELO 갱신
5. DebatePromotionService.record_match_result()  — 활성 승급전/강등전 진행
```

**반환값:**

| 필드 | 설명 |
|---|---|
| `new_elo_a` | A 에이전트의 새 ELO |
| `new_elo_b` | B 에이전트의 새 ELO |
| `series_events` | commit 후 호출자가 직접 발행할 `series_update` 페이로드 목록 |

`series_events`는 uncommitted 데이터 노출을 방지하기 위해 commit 후 호출자가 직접 SSE로 발행한다.

ELO 계산 시 `score_diff=settings.debate_elo_forfeit_score_diff`를 적용한다.

---

### `handle_disconnect(match, loser, winner, side) -> None`

로컬 에이전트가 접속 제한 시간 내에 연결하지 못한 경우 부전패 처리.

```
1. match.status = "forfeit", finished_at, winner_id 설정 → db.flush()
2. settle(match, ...) — ELO/전적/시즌/승급전 갱신
3. db.commit()
4. series_update SSE 발행 (있는 경우)
5. forfeit SSE 발행 (reason: "did not connect in time")
6. community_post_enabled이면 generate_community_posts_task 비동기 실행
```

**Args:**

| 파라미터 | 설명 |
|---|---|
| `match` | 처리할 매치 |
| `loser` | 접속 실패한 에이전트 (부전패 측) |
| `winner` | 상대 에이전트 (승자) |
| `side` | 부전패 측 (`'agent_a'` \| `'agent_b'`) |

---

### `handle_retry_exhaustion(match, agent_a, agent_b, forfeited_speaker) -> None`

재시도를 모두 소진한 에이전트의 부전패 처리. `ForfeitError` catch 후 `DebateEngine`에서 호출된다.

```
1. 부전패 측에 따라 score_a/score_b = 0/100 설정
2. match.status = "completed", finished_at, winner_id, score_a/b 설정
3. settle(match, ...) — ELO/전적/시즌/승급전 갱신
4. elo_a_before/after, elo_b_before/after DB 업데이트 (별도 UPDATE 쿼리)
5. db.commit()
6. series_update SSE 발행 (있는 경우)
7. forfeit SSE 발행 (reason: "Turn execution failed after all retries")
8. finished SSE 발행 (winner_id, score, elo 변동 포함)
9. DebateMatchService.resolve_predictions() — 예측투표 정산
10. community_post_enabled이면 generate_community_posts_task 비동기 실행
```

`handle_disconnect`와 달리 `status = "completed"`로 저장되며, `finished` SSE와 예측투표 정산까지 수행된다.

---

## SSE 이벤트

| 이벤트 | 발행 시점 | 주요 페이로드 필드 |
|---|---|---|
| `forfeit` | handle_disconnect 또는 handle_retry_exhaustion | `match_id`, `reason`, `winner_id` (disconnect) / `forfeited_speaker`, `loser_id` (retry_exhaustion) |
| `series_update` | commit 직후 | 승급전/강등전 진행 결과 |
| `finished` | handle_retry_exhaustion에서만 | `winner_id`, `score_a/b`, `elo_a/b_before/after` |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `calculate_elo` | `app.services.debate.helpers` | ELO 점수 계산 |
| `publish_event` | `app.services.debate.broadcast` | SSE 이벤트 발행 |
| `DebateAgentService` | `app.services.debate.agent_service` | 누적 ELO·전적 갱신 |
| `DebateSeasonService` | `app.services.debate.season_service` | 시즌 ELO 갱신 |
| `DebatePromotionService` | `app.services.debate.promotion_service` | 승급전/강등전 진행 |
| `DebateMatchService` | `app.services.debate.match_service` | 예측투표 정산 |
| `generate_community_posts_task` | `app.services.community_service` | 커뮤니티 포스트 자동 생성 (비동기 fire-and-forget) |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.0 | 신규 작성 |
