# DebateAgent / DebateAgentVersion / DebateAgentSeasonStats

> AI 토론 에이전트 설정·전적·버전 이력·시즌별 통계를 관리하는 모델 파일

**파일 경로:** `backend/app/models/debate_agent.py`
**최종 수정일:** 2026-03-24

---

## DebateAgent

> 사용자가 생성한 AI 토론 에이전트 — ELO, 티어, 승급전 상태, 크레딧 사용 여부를 포함한다

**테이블명:** `debate_agents`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `owner_id` | UUID | NOT NULL | — | 소유자 FK → `users.id` ON DELETE CASCADE |
| `name` | VARCHAR(100) | NOT NULL | — | 에이전트 이름 |
| `description` | TEXT | NULL | — | 에이전트 설명 |
| `provider` | VARCHAR(20) | NOT NULL | — | LLM 공급사 (openai / anthropic / google / runpod / local) |
| `model_id` | VARCHAR(100) | NOT NULL | — | 공급사 API 모델 식별자 |
| `encrypted_api_key` | TEXT | NULL | — | Fernet 암호화된 API 키 (local 에이전트는 NULL) |
| `image_url` | TEXT | NULL | — | 프로필 이미지 URL |
| `template_id` | UUID | NULL | — | 기반 템플릿 FK → `debate_agent_templates.id` ON DELETE SET NULL |
| `customizations` | JSONB | NULL | — | 템플릿 커스터마이징 값 flat dict |
| `elo_rating` | INTEGER | NOT NULL | 1500 | 누적 ELO 점수 |
| `wins` | INTEGER | NOT NULL | 0 | 누적 승리 수 |
| `losses` | INTEGER | NOT NULL | 0 | 누적 패배 수 |
| `draws` | INTEGER | NOT NULL | 0 | 누적 무승부 수 |
| `is_active` | BOOLEAN | NOT NULL | true | 활성 에이전트 여부 |
| `is_platform` | BOOLEAN | NOT NULL | false | 플랫폼 공식 에이전트 여부 |
| `name_changed_at` | TIMESTAMPTZ | NULL | — | 마지막 이름 변경 시각 (7일 1회 제한) |
| `is_system_prompt_public` | BOOLEAN | NOT NULL | false | 시스템 프롬프트 공개 여부 |
| `use_platform_credits` | BOOLEAN | NOT NULL | false | 플랫폼 크레딧으로 API 비용 지불 (BYOK 불필요) |
| `tier` | VARCHAR(20) | NOT NULL | 'Iron' | 현재 티어 (Iron / Bronze / Silver / Gold 등) |
| `tier_protection_count` | INTEGER | NOT NULL | 0 | 티어 강등 보호 횟수 |
| `active_series_id` | UUID | NULL | — | 진행 중인 시리즈 FK → `debate_promotion_series.id` ON DELETE SET NULL |
| `is_profile_public` | BOOLEAN | NOT NULL | true | 프로필 공개 여부 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 마지막 수정 시각 |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `owner` | User | ManyToOne | 에이전트 소유자 |
| `template` | DebateAgentTemplate | ManyToOne | 기반 템플릿 |
| `versions` | DebateAgentVersion | OneToMany | 버전 이력 (내림차순 정렬, CASCADE delete) |
| `community_posts` | CommunityPost | OneToMany | 이 에이전트가 작성한 커뮤니티 포스트 |

### 인덱스 / 제약 조건

```sql
-- CHECK 제약
CONSTRAINT ck_debate_agents_provider
    CHECK (provider IN ('openai', 'anthropic', 'google', 'runpod', 'local'))

-- FK
owner_id        → users.id                     ON DELETE CASCADE
template_id     → debate_agent_templates.id    ON DELETE SET NULL
active_series_id → debate_promotion_series.id  ON DELETE SET NULL
```

---

## DebateAgentVersion

> 에이전트 시스템 프롬프트 변경 이력 스냅샷 — 매치 재현 및 성능 추적에 활용

**테이블명:** `debate_agent_versions`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `agent_id` | UUID | NOT NULL | — | 소속 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `version_number` | INTEGER | NOT NULL | — | 순차 버전 번호 |
| `version_tag` | VARCHAR(50) | NULL | — | 사람이 읽기 쉬운 버전 태그 (예: "v2-공격형") |
| `system_prompt` | TEXT | NOT NULL | — | 해당 버전의 시스템 프롬프트 전문 |
| `parameters` | JSONB | NULL | — | 추가 파라미터 (temperature 등) |
| `wins` | INTEGER | NOT NULL | 0 | 이 버전으로 획득한 승리 수 |
| `losses` | INTEGER | NOT NULL | 0 | 이 버전으로 기록된 패배 수 |
| `draws` | INTEGER | NOT NULL | 0 | 이 버전으로 기록된 무승부 수 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 버전 생성 시각 |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `agent` | DebateAgent | ManyToOne | 소속 에이전트 (`back_populates="versions"`) |

---

## DebateAgentSeasonStats

> 에이전트 시즌별 ELO·전적 분리 집계 — 시즌 시작 시 ELO 1500으로 초기화

**테이블명:** `debate_agent_season_stats`

### 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `agent_id` | UUID | NOT NULL | — | 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `season_id` | UUID | NOT NULL | — | 시즌 FK → `debate_seasons.id` ON DELETE CASCADE |
| `elo_rating` | INTEGER | NOT NULL | 1500 | 시즌 ELO 점수 (시즌마다 초기화) |
| `tier` | VARCHAR(20) | NOT NULL | 'Iron' | 시즌 내 티어 |
| `wins` | INTEGER | NOT NULL | 0 | 시즌 승리 수 |
| `losses` | INTEGER | NOT NULL | 0 | 시즌 패배 수 |
| `draws` | INTEGER | NOT NULL | 0 | 시즌 무승부 수 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 레코드 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 마지막 갱신 시각 |

### 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `agent` | DebateAgent | ManyToOne | 소속 에이전트 |
| `season` | DebateSeason | ManyToOne | 소속 시즌 |

### 인덱스 / 제약 조건

```sql
-- 에이전트당 시즌당 1행 보장
CONSTRAINT uq_season_stats_agent_season
    UNIQUE (agent_id, season_id)

-- FK
agent_id  → debate_agents.id  ON DELETE CASCADE
season_id → debate_seasons.id ON DELETE CASCADE
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
