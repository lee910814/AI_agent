# DebatePromotionService

> ELO 티어 경계 통과 시 즉시 승급/강등 대신 시리즈(승급전·강등전)를 생성하여 결과에 따라 티어를 결정하는 서비스

**파일 경로:** `backend/app/services/debate/promotion_service.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

ELO 레이팅이 티어 경계를 넘을 때 즉시 티어를 변경하는 대신 시리즈를 생성하여 결과에 따라 티어를 결정한다.

- **승급전**: 3판 2선승 (`required_wins=2`). 2승 먼저 달성하면 상위 티어로 승급
- **강등전**: 1판 필승 (`required_wins=1`). 1승을 달성하면 현재 티어 유지, 실패하면 강등
- 이미 활성 시리즈가 진행 중이면 중복 시리즈를 생성하지 않는다
- `tier_protection_count > 0`이면 강등전을 생성하지 않고 보호 횟수만 소진한다

---

## 주요 상수

| 상수 | 타입 | 값 / 설명 |
|---|---|---|
| `TIER_ORDER` | `list[str]` | `["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]` — 티어 순서. 인덱스가 낮을수록 하위 티어. `new_idx > old_idx` → 승급, `new_idx < old_idx` → 강등 방향 판별에 사용 |

---

## 클래스: DebatePromotionService

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
| `get_active_series` | `(agent_id: str) -> DebatePromotionSeries \| None` | 에이전트의 현재 활성(`status="active"`) 시리즈 조회 |
| `get_series_history` | `(agent_id: str, limit: int = 20, offset: int = 0) -> list[DebatePromotionSeries]` | 시리즈 이력 조회 (`created_at DESC` 정렬) |
| `create_promotion_series` | `(agent_id: str, from_tier: str, to_tier: str) -> DebatePromotionSeries` | 승급전 시리즈 생성 (`required_wins=2`, 3판 2선승) |
| `create_demotion_series` | `(agent_id: str, from_tier: str, to_tier: str) -> DebatePromotionSeries` | 강등전 시리즈 생성 (`required_wins=1`, 1판 필승) |
| `record_match_result` | `(series_id: str, result: str) -> dict` | 시리즈에 매치 결과(`'win'`/`'loss'`/`'draw'`) 기록. 종료 조건 충족 시 티어 변경·에이전트 상태 갱신 |
| `cancel_series` | `(agent_id: str) -> None` | 활성 시리즈를 `"cancelled"` 상태로 전환. 에이전트 `active_series_id` 초기화 |
| `check_and_trigger` | `(agent_id: str, old_elo: int, new_elo: int, current_tier: str, protection_count: int) -> DebatePromotionSeries \| None` | ELO 변화로 승급전/강등전 트리거 여부 확인 후 시리즈 생성. 생성하지 않으면 `None` |
| `_create_series` | `(agent_id: str, series_type: str, from_tier: str, to_tier: str, required_wins: int) -> DebatePromotionSeries` | 시리즈 생성 공통 로직. `flush()`로 ID 확보 후 `DebateAgent.active_series_id` 갱신 |

### `record_match_result` draw 처리

`result == "draw"`이면 `draw_count`를 증가시킨다.

- `draw_count >= settings.debate_series_max_draws`에 도달하면 시리즈 상태를 `"expired"`로 전환하고 `DebateAgent.active_series_id`를 `None`으로 초기화한다. 티어는 변경되지 않는다.
- `max_draws` 미만이면 시리즈를 계속 진행한다.

### `record_match_result` 종료 조건 (win/loss)

`max_losses` 계산 공식:
- 강등전: `max_losses = 0` (1판 필승, 1패 즉시 강등)
- 승급전: `max_losses = 3 - required_wins = 1` (3판 2선승, 1패까지 허용)

| 시리즈 유형 | `required_wins` | `max_losses` | 종료 조건 |
|---|---|---|---|
| 승급전 | 2 | 1 | `current_wins >= 2` → 시리즈 승리 / `current_losses > 1` → 시리즈 패배 |
| 강등전 | 1 | 0 | `current_wins >= 1` → 시리즈 승리 / `current_losses > 0` → 시리즈 패배 |

### 시리즈 종료 시 에이전트 상태 변경

| 상황 | `tier` | `tier_protection_count` | `active_series_id` |
|---|---|---|---|
| 승급전 승리 | `to_tier`로 변경 | `3` | `None` |
| 승급전 패배 | 변경 없음 | 변경 없음 | `None` |
| 강등전 승리 | 변경 없음 | `1` (보상) | `None` |
| 강등전 패배 | `to_tier`로 변경 | 변경 없음 | `None` |

### `check_and_trigger` 트리거 조건

| 조건 | 결과 |
|---|---|
| `old_tier == new_tier` (ELO가 같은 티어 범위) | 트리거 없음, `None` 반환 |
| 이미 활성 시리즈 존재 | 중복 생성 방지, `None` 반환 |
| 승급 방향 + `old_tier != "Master"` | `create_promotion_series()` 호출 |
| 승급 방향 + `old_tier == "Master"` | 최상위 티어, 트리거 없음 |
| 강등 방향 + `old_tier != "Iron"` + `protection_count == 0` | `create_demotion_series()` 호출 |
| 강등 방향 + `protection_count > 0` | 보호 횟수 1 차감 후 `None` 반환 (`DebateAgent.tier_protection_count -= 1` 직접 실행, 호출자 별도 처리 불필요) |
| 강등 방향 + `old_tier == "Iron"` | 최하위 티어, 트리거 없음 |

### `record_match_result` 반환 dict 구조

```python
{
    "id": str,                   # series UUID (series_id와 동일값)
    "series_id": str,
    "agent_id": str,
    "series_type": str,          # "promotion" | "demotion"
    "status": str,               # "active" | "won" | "lost" | "expired"
    "current_wins": int,
    "current_losses": int,
    "draw_count": int,
    "required_wins": int,
    "from_tier": str,
    "to_tier": str,
    "tier_changed": bool,
    "new_tier": str | None,      # tier_changed=True일 때만 값 있음
}
```

시리즈를 찾을 수 없거나 이미 완료/취소된 경우 `{"status": "not_found"}` 반환.

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `DebateAgent` | `app.models.debate_agent` | 에이전트 ORM 모델. `tier`, `tier_protection_count`, `active_series_id` 갱신 |
| `DebatePromotionSeries` | `app.models.debate_promotion_series` | 시리즈 ORM 모델. 생성·상태 갱신 |
| `get_tier_from_elo` | `app.services.debate.agent_service` | ELO로 티어 문자열 계산 (지연 임포트 — 순환 참조 방지) |

---

## 호출 흐름

### 시리즈 생성 흐름

```
engine.py (_finalize_match 또는 _handle_forfeit)
  → DebateAgentService.update_elo(agent_id, new_elo, result_type)
      → [active_series_id 없음]
          → DebatePromotionService.check_and_trigger(agent_id, old_elo, new_elo, tier, protection_count)
              → get_tier_from_elo(new_elo) 로 new_tier 계산
              → [old_idx != new_idx] get_active_series() — 중복 확인
              → create_promotion_series() 또는 create_demotion_series()
                  → _create_series()
                      → DebatePromotionSeries INSERT + flush()
                      → UPDATE debate_agents SET active_series_id = series.id
```

### 시리즈 매치 결과 기록 흐름

```
engine.py (시리즈 소속 매치 완료 시)
  → DebatePromotionService.record_match_result(series_id, result)
      → 승/패 카운터 증가
      → 종료 조건 충족 시:
          series.status = "won" | "lost"
          UPDATE debate_agents (tier, tier_protection_count, active_series_id)
```

### 매칭 시 시리즈 참조 흐름

```
matching_service.py (ready_up)
  → DebatePromotionService.get_active_series(agent_id)
      → 시리즈 존재 시 match.series_id 태깅
```

---

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| `record_match_result` — 시리즈 미존재 또는 이미 완료된 경우 | `{"status": "not_found"}` 반환 (예외 미발생, 중복 처리 방지) |
| `cancel_series` — 활성 시리즈 없음 | 즉시 `return` (예외 미발생) |

예외는 발생시키지 않고 안전하게 처리하는 설계. 호출자(`engine.py`, `agent_service.py`)가 반환값을 보고 후속 처리를 결정한다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | `record_match_result` 반환 dict에 `id`, `agent_id`, `draw_count` 필드 추가. `draw` 처리 로직 및 `expired` 상태 문서화. 강등전 `max_losses` 수정 (2→0). `check_and_trigger` 보호 횟수 소진 처리 주체 정정 (호출자→서비스 직접 처리). `record_match_result` `result` 파라미터에 `'draw'` 추가 |
| 2026-03-12 | 규칙 준수 전면 재작성. H2 섹션 순서 정렬, 표 형식 통일, 트리거 조건 표 확장, 에러 처리 섹션 추가 |
| 2026-03-11 | 실제 코드 기반으로 초기 재작성 |
