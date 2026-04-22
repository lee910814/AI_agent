# DebateSeasonService

> 시즌 생성·활성 시즌 조회·시즌별 ELO 집계·시즌 종료(결과 저장·보상 지급·누적 ELO soft reset)를 담당하는 서비스

**파일 경로:** `backend/app/services/debate/season_service.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

토론 시즌 전체 생명주기를 관리한다.

- **시즌 생성/조회** — 시즌 생성, 활성/현재 시즌 조회
- **시즌별 ELO·전적 분리 집계** — 누적 ELO와 독립된 `DebateAgentSeasonStats` 테이블에 시즌 전적 기록. 동시 INSERT 충돌을 SAVEPOINT로 처리
- **시즌 종료** — 참가 에이전트 순위 결정, 순위별 보상 크레딧 지급, 누적 ELO soft reset(`(elo + 1500) // 2`), 시즌 결과 스냅샷 저장

---

## 주요 상수

없음

---

## 클래스: DebateSeasonService

### 생성자

```python
def __init__(self, db: AsyncSession)
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `db` | `AsyncSession` | SQLAlchemy 비동기 세션. FastAPI `Depends(get_db)`로 주입 |

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `create_season` | `(season_number: int, title: str, start_at: datetime, end_at: datetime) -> DebateSeason` | 시즌 생성 (`status="upcoming"`). `commit` + `refresh` 포함 |
| `get_active_season` | `() -> DebateSeason \| None` | `status="active"` 시즌만 반환. `upcoming` 제외. `season_number DESC` 기준 최신 1건 |
| `get_current_season` | `() -> DebateSeason \| None` | `active` 우선, 없으면 최신 `upcoming`. `sa_case`로 단일 쿼리 통합 |
| `get_or_create_season_stats` | `(agent_id: str, season_id: str) -> DebateAgentSeasonStats` | 에이전트의 시즌 통계 행 조회 또는 생성 (초기값: `elo_rating=1500`, `tier="Iron"`). `begin_nested()` SAVEPOINT로 동시 INSERT 충돌 처리 |
| `update_season_stats` | `(agent_id: str, season_id: str, new_elo: int, result_type: str) -> None` | 시즌 ELO·전적 갱신 + `get_tier_from_elo(new_elo)`로 tier 재계산. `result_type`: `'win'`/`'loss'`/`'draw'` |
| `get_season_results` | `(season_id: str) -> list[dict]` | 시즌 최종 순위 조회 (`rank ASC`). `DebateSeasonResult JOIN DebateAgent` |
| `close_season` | `(season_id: str) -> None` | 시즌 종료 5단계 처리. 활성 상태가 아니면 `ValueError` 발생 |

### `close_season` 5단계 처리

```
1. 시즌 검증
   → season.status == "active" 확인. 아니면 ValueError 발생

2. 시즌 참가 에이전트 조회
   → DebateAgentSeasonStats JOIN DebateAgent
   → season_id 일치 + is_active=True
   → elo_rating DESC 정렬 (순위 결정)
   → 매치 0회 에이전트 미포함 (stats 행 없음 = 매치 없음)

3. 보상 지급 대상 User 배치 조회 (N+1 방지)
   → 모든 에이전트의 owner_id를 수집 → 단일 IN 쿼리로 User 조회 → id → User 맵 구성

4. 각 에이전트 순위별 처리 (rank 1부터 순차)
   → DebateSeasonResult INSERT (시즌 ELO/전적 기준 스냅샷)
   → reward > 0이면 User.credit_balance += reward (배치 맵 O(1) 접근)
   → 누적 ELO soft reset: agent.elo_rating = (agent.elo_rating + 1500) // 2
   → 누적 tier 재계산: agent.tier = get_tier_from_elo(new_elo)

5. season.status = "completed" → commit()
```

### 보상 기준 (`settings`에서 설정)

| 설정 키 | 설명 |
|---|---|
| `debate_season_reward_top3` | 1~3위 보상 크레딧 리스트 (예: `[1000, 500, 300]`) |
| `debate_season_reward_rank4_10` | 4~10위 보상 크레딧. 11위 이하는 0 |

### `get_season_results` 반환 dict 구조 (항목당)

```python
{
    "rank": int,
    "agent_id": str,
    "agent_name": str,
    "agent_image_url": str | None,
    "final_elo": int,
    "final_tier": str,
    "wins": int,
    "losses": int,
    "draws": int,
    "reward_credits": int,
}
```

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `DebateAgent`, `DebateAgentSeasonStats` | `app.models.debate_agent` | 에이전트·시즌 통계 ORM 모델. ELO soft reset 대상 |
| `DebateSeason`, `DebateSeasonResult` | `app.models.debate_season` | 시즌·결과 ORM 모델 |
| `User` | `app.models.user` | 보상 크레딧 지급 (`credit_balance` 갱신) |
| `settings` | `app.core.config` | 보상 크레딧 기준값 읽기 |
| `get_tier_from_elo` | `app.services.debate.agent_service` | ELO로 티어 문자열 계산 |

---

## 호출 흐름

### 시즌 생성 및 종료 흐름

```
API 라우터 (api/admin/debate/seasons.py)
  → DebateSeasonService.create_season(season_number, title, start_at, end_at)
      → DebateSeason INSERT + commit() + refresh()

  → DebateSeasonService.close_season(season_id)
      → (4단계 처리 — 위 참조)
      → commit()
```

### 매칭 시 활성 시즌 태깅 흐름

```
matching_service.py (ready_up)
  → DebateSeasonService.get_active_season()
      → [시즌 존재 시] match.season_id = season.id 태깅
```

### 매치 완료 후 시즌 통계 갱신 흐름

```
engine.py (_finalize_match)
  → [match.season_id 있음]
      → DebateSeasonService.update_season_stats(agent_a_id, season_id, new_elo_a, result_a)
          → get_or_create_season_stats(agent_a_id, season_id)
              → [stats 없음] begin_nested() → DebateAgentSeasonStats INSERT
              → [IntegrityError] 재조회 (동시 삽입 충돌 처리)
          → stats.elo_rating = new_elo_a
          → stats.tier = get_tier_from_elo(new_elo_a)
          → stats.wins/losses/draws += 1
      → DebateSeasonService.update_season_stats(agent_b_id, season_id, new_elo_b, result_b)
```

---

## 에러 처리

| 상황 | 예외 | 발생 메서드 |
|---|---|---|
| 시즌 미존재 | `ValueError("Season not found")` | `close_season` |
| 활성 상태가 아닌 시즌 종료 시도 | `ValueError("활성 시즌만 종료할 수 있습니다")` | `close_season` |
| `get_or_create_season_stats` 동시 INSERT 충돌 | `IntegrityError` 포착 → 재조회로 안전 처리 | `get_or_create_season_stats` |

`close_season`의 예외는 `api/admin/debate/seasons.py` 라우터가 `ValueError` → HTTP 400으로 변환한다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | `close_season` 단계 수 수정 (4단계 → 5단계). 메서드 표의 단계 수 동기화 |
| 2026-03-12 | 규칙 준수 전면 재작성. H2 섹션 순서 정렬, 주요 상수 섹션 추가, close_season 처리 단계 상세화, 호출 흐름 3개 시나리오로 확장, 에러 처리 표 보강 |
| 2026-03-11 | 실제 코드 기반으로 초기 재작성 |
