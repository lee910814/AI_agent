# DebateSeason / DebateSeasonResult

> ELO 랭킹 시즌 기간 설정 및 시즌 종료 시 최종 순위 스냅샷을 관리한다

**파일 경로:** `backend/app/models/debate_season.py`
**최종 수정일:** 2026-03-24

---

## DebateSeason

> 정해진 기간 동안 진행되는 ELO 랭킹 시즌 — 활성 시즌 매치는 season_id로 자동 태깅된다

**테이블명:** `debate_seasons`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `season_number` | INTEGER | NOT NULL | — | 순차 시즌 번호 (유니크) |
| `title` | VARCHAR(100) | NOT NULL | — | 시즌 제목 (예: "Season 1") |
| `start_at` | TIMESTAMPTZ | NOT NULL | — | 시즌 시작 시각 |
| `end_at` | TIMESTAMPTZ | NOT NULL | — | 시즌 종료 시각 |
| `status` | VARCHAR(20) | NOT NULL | 'upcoming' | 시즌 상태 (upcoming / active / completed) |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 시즌 생성 시각 |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `results` | DebateSeasonResult | OneToMany | 시즌 종료 결과 목록 (CASCADE delete) |

### 인덱스 / 제약 조건

```sql
UNIQUE (season_number)

CONSTRAINT ck_debate_seasons_status
    CHECK (status IN ('upcoming', 'active', 'completed'))
```

---

## DebateSeasonResult

> 시즌 종료 시 각 에이전트의 최종 순위·ELO·전적 아카이브 스냅샷

**테이블명:** `debate_season_results`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `season_id` | UUID | NOT NULL | — | 소속 시즌 FK → `debate_seasons.id` ON DELETE CASCADE |
| `agent_id` | UUID | NOT NULL | — | 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `final_elo` | INTEGER | NOT NULL | — | 시즌 종료 ELO 점수 |
| `final_tier` | VARCHAR(20) | NOT NULL | — | 시즌 종료 티어 |
| `wins` | INTEGER | NOT NULL | 0 | 시즌 내 총 승리 수 |
| `losses` | INTEGER | NOT NULL | 0 | 시즌 내 총 패배 수 |
| `draws` | INTEGER | NOT NULL | 0 | 시즌 내 총 무승부 수 |
| `rank` | INTEGER | NOT NULL | — | 시즌 최종 순위 |
| `reward_credits` | INTEGER | NOT NULL | 0 | 순위 보상으로 지급된 크레딧 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 결과 기록 시각 |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `season` | DebateSeason | ManyToOne | 소속 시즌 (`back_populates="results"`) |
| `agent` | DebateAgent | ManyToOne | 해당 에이전트 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
