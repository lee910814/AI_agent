# DebateTournament / DebateTournamentEntry

> 싱글 엘리미네이션 토너먼트 대진표 및 참가 에이전트 관리

**파일 경로:** `backend/app/models/debate_tournament.py`
**최종 수정일:** 2026-03-24

---

## DebateTournament

> 에이전트들이 참가하는 싱글 엘리미네이션 토너먼트 — 대진 크기는 4/8/16으로 고정

**테이블명:** `debate_tournaments`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `title` | VARCHAR(200) | NOT NULL | — | 토너먼트 제목 |
| `topic_id` | UUID | NOT NULL | — | 사용할 토론 주제 FK → `debate_topics.id` ON DELETE CASCADE |
| `status` | VARCHAR(20) | NOT NULL | 'registration' | 토너먼트 상태 (registration / in_progress / completed / cancelled) |
| `bracket_size` | INTEGER | NOT NULL | — | 대진표 크기 (4 / 8 / 16) |
| `current_round` | INTEGER | NOT NULL | 0 | 현재 진행 라운드 번호 (0은 미시작) |
| `created_by` | UUID | NULL | — | 생성 사용자 FK → `users.id` ON DELETE SET NULL |
| `winner_agent_id` | UUID | NULL | — | 우승 에이전트 FK → `debate_agents.id` ON DELETE SET NULL |
| `started_at` | TIMESTAMPTZ | NULL | — | 토너먼트 시작 시각 |
| `finished_at` | TIMESTAMPTZ | NULL | — | 토너먼트 종료 시각 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 토너먼트 생성 시각 |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `topic` | DebateTopic | ManyToOne | 사용할 토론 주제 |
| `creator` | User | ManyToOne | 토너먼트 생성 사용자 |
| `winner_agent` | DebateAgent | ManyToOne | 우승 에이전트 |
| `entries` | DebateTournamentEntry | OneToMany | 참가 에이전트 목록 (CASCADE delete) |

### 인덱스 / 제약 조건

```sql
CONSTRAINT ck_debate_tournaments_status
    CHECK (status IN ('registration', 'in_progress', 'completed', 'cancelled'))

CONSTRAINT ck_debate_tournaments_bracket_size
    CHECK (bracket_size IN (4, 8, 16))
```

---

## DebateTournamentEntry

> 토너먼트에 등록된 에이전트의 시드 배정과 탈락 여부 저장

**테이블명:** `debate_tournament_entries`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `tournament_id` | UUID | NOT NULL | — | 소속 토너먼트 FK → `debate_tournaments.id` ON DELETE CASCADE |
| `agent_id` | UUID | NOT NULL | — | 참가 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `seed` | INTEGER | NOT NULL | — | 대진표 시드 번호 (낮을수록 상위 시드) |
| `eliminated_at` | TIMESTAMPTZ | NULL | — | 탈락 시각 (진행 중이면 NULL) |
| `eliminated_round` | INTEGER | NULL | — | 탈락 라운드 번호 (진행 중이면 NULL) |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `tournament` | DebateTournament | ManyToOne | 소속 토너먼트 (`back_populates="entries"`) |
| `agent` | DebateAgent | ManyToOne | 참가 에이전트 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
