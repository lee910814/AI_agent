# DebatePromotionSeries

> 에이전트 티어 변동을 결정하는 승급전/강등전 다전제 시리즈 진행 상태를 저장한다

**파일 경로:** `backend/app/models/debate_promotion_series.py`
**테이블명:** `debate_promotion_series`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `agent_id` | UUID | NOT NULL | — | 대상 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `series_type` | VARCHAR(20) | NOT NULL | — | 시리즈 유형 (promotion / demotion) |
| `from_tier` | VARCHAR(20) | NOT NULL | — | 시리즈 시작 전 티어 |
| `to_tier` | VARCHAR(20) | NOT NULL | — | 성공 시 이동할 티어 |
| `required_wins` | INTEGER | NOT NULL | — | 시리즈 통과에 필요한 최소 승리 수 |
| `current_wins` | INTEGER | NOT NULL | 0 | 현재까지 획득한 승리 수 |
| `current_losses` | INTEGER | NOT NULL | 0 | 현재까지 기록된 패배 수 |
| `draw_count` | INTEGER | NOT NULL | 0 | 현재까지 기록된 무승부 수 |
| `status` | VARCHAR(20) | NOT NULL | 'active' | 시리즈 상태 (active / won / lost / cancelled / expired) |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 시리즈 생성 시각 |
| `completed_at` | TIMESTAMPTZ | NULL | — | 시리즈 종료 시각 (진행 중이면 NULL) |

---

## 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `agent` | DebateAgent | ManyToOne | 시리즈 대상 에이전트 |

---

## 인덱스 / 제약 조건

```sql
CONSTRAINT ck_promotion_series_type
    CHECK (series_type IN ('promotion', 'demotion'))

CONSTRAINT ck_promotion_series_status
    CHECK (status IN ('active', 'won', 'lost', 'cancelled', 'expired'))

-- FK
agent_id → debate_agents.id ON DELETE CASCADE
```

---

## 비고

- 승급전: `required_wins = 2` (3판 2선승)
- 강등전: `required_wins = 1` (1판 필승)
- 진행 중인 시리즈 UUID는 `DebateAgent.active_series_id`에 캐싱되어 매칭 시 빠르게 조회된다
- `DebateMatch.series_id`로 시리즈에 속한 매치를 추적한다

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
