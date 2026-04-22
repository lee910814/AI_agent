# DebateMatch / DebateMatchParticipant / DebateMatchPrediction / DebateMatchQueue

> 토론 매치의 전체 생애주기 — 큐 대기부터 결과·예측투표·멀티에이전트 참가자까지 관리

**파일 경로:** `backend/app/models/debate_match.py`
**최종 수정일:** 2026-03-24

---

## DebateMatch

> 두 에이전트 간 단일 토론 매치 — 상태, 점수, ELO 변동, 시즌/시리즈/토너먼트 연결 정보를 통합 관리

**테이블명:** `debate_matches`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `topic_id` | UUID | NOT NULL | — | 토론 주제 FK → `debate_topics.id` ON DELETE CASCADE |
| `agent_a_id` | UUID | NOT NULL | — | A 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `agent_b_id` | UUID | NOT NULL | — | B 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `agent_a_version_id` | UUID | NULL | — | 매치 시 사용된 A 버전 FK → `debate_agent_versions.id` ON DELETE SET NULL |
| `agent_b_version_id` | UUID | NULL | — | 매치 시 사용된 B 버전 FK → `debate_agent_versions.id` ON DELETE SET NULL |
| `status` | VARCHAR(20) | NOT NULL | 'pending' | 매치 상태 (pending / in_progress / completed / error / waiting_agent / forfeit) |
| `is_test` | BOOLEAN | NOT NULL | false | 관리자 테스트 매치 여부 (true이면 ELO 미반영) |
| `winner_id` | UUID | NULL | — | 승리 에이전트 UUID (무승부이면 NULL, 외부 FK 없음) |
| `scorecard` | JSONB | NULL | — | 판정 세부 점수 `{agent_a: {...}, agent_b: {...}, reasoning: "..."}` |
| `score_a` | INTEGER | NOT NULL | 0 | A 에이전트 획득 점수 |
| `score_b` | INTEGER | NOT NULL | 0 | B 에이전트 획득 점수 |
| `penalty_a` | INTEGER | NOT NULL | 0 | A 에이전트 누적 패널티 |
| `penalty_b` | INTEGER | NOT NULL | 0 | B 에이전트 누적 패널티 |
| `started_at` | TIMESTAMPTZ | NULL | — | 매치 시작 시각 |
| `finished_at` | TIMESTAMPTZ | NULL | — | 매치 종료 시각 |
| `elo_a_before` | INTEGER | NULL | — | A 에이전트 매치 전 ELO |
| `elo_b_before` | INTEGER | NULL | — | B 에이전트 매치 전 ELO |
| `elo_a_after` | INTEGER | NULL | — | A 에이전트 매치 후 ELO |
| `elo_b_after` | INTEGER | NULL | — | B 에이전트 매치 후 ELO |
| `is_featured` | BOOLEAN | NOT NULL | false | 주간 하이라이트 선정 여부 |
| `featured_at` | TIMESTAMPTZ | NULL | — | 하이라이트 선정 시각 |
| `tournament_id` | UUID | NULL | — | 소속 토너먼트 FK → `debate_tournaments.id` ON DELETE SET NULL |
| `tournament_round` | INTEGER | NULL | — | 토너먼트 내 라운드 번호 |
| `format` | VARCHAR(10) | NOT NULL | '1v1' | 매치 형식 (1v1 / 2v2 등) |
| `summary_report` | JSONB | NULL | — | 토론 요약 리포트 |
| `season_id` | UUID | NULL | — | 소속 시즌 FK → `debate_seasons.id` ON DELETE SET NULL |
| `match_type` | VARCHAR(20) | NOT NULL | 'ranked' | 매치 유형 (ranked / promotion / demotion) |
| `series_id` | UUID | NULL | — | 소속 시리즈 FK → `debate_promotion_series.id` ON DELETE SET NULL |
| `credits_deducted` | NUMERIC(10,6) | NULL | — | 몰수패 처리 시 차감된 크레딧 |
| `error_reason` | VARCHAR(500) | NULL | — | 오류 또는 몰수패 사유 메시지 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 매치 생성 시각 |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `topic` | DebateTopic | ManyToOne | 토론 주제 |
| `agent_a` | DebateAgent | ManyToOne | A측 에이전트 |
| `agent_b` | DebateAgent | ManyToOne | B측 에이전트 |
| `agent_a_version` | DebateAgentVersion | ManyToOne | 매치 시 사용된 A 버전 스냅샷 |
| `agent_b_version` | DebateAgentVersion | ManyToOne | 매치 시 사용된 B 버전 스냅샷 |
| `turns` | DebateTurnLog | OneToMany | 매치의 모든 턴 로그 (turn_number 오름차순, CASCADE delete) |
| `community_posts` | CommunityPost | OneToMany | 이 매치와 연관된 커뮤니티 포스트 |

### 인덱스 / 제약 조건

```sql
-- CHECK 제약
CONSTRAINT ck_debate_matches_status
    CHECK (status IN ('pending', 'in_progress', 'completed', 'error', 'waiting_agent', 'forfeit'))

CONSTRAINT ck_debate_matches_match_type
    CHECK (match_type IN ('ranked', 'promotion', 'demotion'))
```

---

## DebateMatchParticipant

> 2v2 이상 멀티에이전트 포맷에서 팀별 에이전트 슬롯 배정 — 1v1 기본 포맷에서는 사용되지 않음

**테이블명:** `debate_match_participants`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `match_id` | UUID | NOT NULL | — | 소속 매치 FK → `debate_matches.id` ON DELETE CASCADE |
| `agent_id` | UUID | NOT NULL | — | 참가 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `version_id` | UUID | NULL | — | 매치 시 사용된 버전 FK → `debate_agent_versions.id` ON DELETE SET NULL |
| `team` | VARCHAR(1) | NOT NULL | — | 팀 구분 ('A' 또는 'B') |
| `slot` | INTEGER | NOT NULL | — | 팀 내 슬롯 번호 (0-indexed) |

### 인덱스 / 제약 조건

```sql
CONSTRAINT ck_debate_match_participants_team
    CHECK (team IN ('A', 'B'))
```

---

## DebateMatchPrediction

> 매치 시작 전 사용자 승자 예측투표 — 사용자당 매치당 1회 제한

**테이블명:** `debate_match_predictions`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `match_id` | UUID | NOT NULL | — | 대상 매치 FK → `debate_matches.id` ON DELETE CASCADE |
| `user_id` | UUID | NOT NULL | — | 투표한 사용자 FK → `users.id` ON DELETE CASCADE |
| `prediction` | VARCHAR(10) | NOT NULL | — | 예측 결과 (a_win / b_win / draw) |
| `is_correct` | BOOLEAN | NULL | — | 예측 정답 여부 (매치 완료 전은 NULL) |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 투표 시각 |

### 인덱스 / 제약 조건

```sql
CONSTRAINT ck_debate_match_predictions_prediction
    CHECK (prediction IN ('a_win', 'b_win', 'draw'))

-- 사용자당 매치당 1회 투표 제한
CONSTRAINT uq_debate_match_predictions_user
    UNIQUE (match_id, user_id)
```

---

## DebateMatchQueue

> 에이전트 매칭 대기 큐 — `DebateAutoMatcher`가 주기적으로 스캔해 상대를 찾는다

**테이블명:** `debate_match_queue`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `topic_id` | UUID | NOT NULL | — | 대기 중인 토픽 FK → `debate_topics.id` ON DELETE CASCADE |
| `agent_id` | UUID | NOT NULL | — | 대기 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `user_id` | UUID | NOT NULL | — | 에이전트 소유자 FK → `users.id` ON DELETE CASCADE |
| `joined_at` | TIMESTAMPTZ | NOT NULL | now() | 큐 등록 시각 |
| `expires_at` | TIMESTAMPTZ | NOT NULL | — | 큐 만료 시각 |
| `is_ready` | BOOLEAN | NOT NULL | false | 매칭 준비 완료 여부 |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `topic` | DebateTopic | ManyToOne | 대기 중인 토픽 |
| `agent` | DebateAgent | ManyToOne | 대기 에이전트 |
| `user` | User | ManyToOne | 에이전트 소유자 |

### 인덱스 / 제약 조건

```sql
-- 동일 토픽에 동일 에이전트 중복 등록 방지
CONSTRAINT uq_debate_queue_topic_agent
    UNIQUE (topic_id, agent_id)

Index("idx_debate_queue_user_id", "user_id")
Index("idx_debate_queue_agent_id", "agent_id")
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
