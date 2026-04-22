# 백엔드 개발자 가이드

**작성일:** 2026-03-10
**대상:** 프로젝트에 합류하는 백엔드 개발자
**스택:** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16 + Redis

---

## 목차

1. [프로젝트 구조](#1-프로젝트-구조)
2. [API 라우터 계층](#2-api-라우터-계층)
3. [서비스 계층](#3-서비스-계층)
4. [데이터베이스 모델](#4-데이터베이스-모델)
5. [토론 엔진](#5-토론-엔진)
6. [SSE 브로드캐스팅](#6-sse-브로드캐스팅)
7. [LLM 호출 규칙](#7-llm-호출-규칙)
8. [인증 및 RBAC](#8-인증-및-rbac)
9. [환경 변수 관리](#9-환경-변수-관리)
10. [테스트 실행](#10-테스트-실행)
11. [개발 규칙 및 주의사항](#11-개발-규칙-및-주의사항)

---

## 1. 프로젝트 구조

```
backend/
├── app/
│   ├── main.py                    # FastAPI 앱 초기화, 라우터 등록, lifespan 이벤트
│   ├── api/                       # 라우터 계층 (HTTP 입출력만 담당)
│   │   ├── auth.py                # /api/auth/*
│   │   ├── debate_agents.py       # /api/agents/*
│   │   ├── debate_matches.py      # /api/matches/*
│   │   ├── debate_topics.py       # /api/topics/*
│   │   ├── debate_tournaments.py  # /api/tournaments/*
│   │   ├── debate_ws.py           # /api/ws/debate/* (WebSocket)
│   │   ├── models.py              # /api/models/*
│   │   ├── uploads.py             # /api/uploads/*
│   │   ├── usage.py               # /api/usage/*
│   │   ├── health.py              # /health
│   │   └── admin/
│   │       ├── debate/            # /api/admin/debate/* (topics, matches, agents, seasons, tournaments, templates)
│   │       └── system/            # /api/admin/* (users, llm_models, monitoring, usage)
│   ├── core/
│   │   ├── config.py              # BaseSettings — 환경 변수 전체 관리
│   │   ├── database.py            # SQLAlchemy async 엔진 + 세션 팩토리
│   │   ├── redis.py               # Redis 공유 클라이언트 (pub/sub + cache)
│   │   ├── auth.py                # JWT 발급/검증, 토큰 블랙리스트
│   │   ├── deps.py                # FastAPI Depends (get_db, get_current_user 등)
│   │   ├── encryption.py          # Fernet 대칭 암호화 (BYOK API 키 저장용)
│   │   ├── exceptions.py          # AppError 계층 (NotFoundError, ForbiddenError 등)
│   │   ├── observability.py       # Langfuse + Sentry + Prometheus 초기화
│   │   └── rate_limit.py          # Redis 슬라이딩 윈도우 Rate Limiter
│   ├── models/                    # SQLAlchemy ORM 모델 (22개 테이블)
│   ├── schemas/                   # Pydantic v2 입출력 스키마
│   └── services/                  # 비즈니스 로직 (라우터에서 직접 DB 쿼리 금지)
│       ├── debate/                # 토론 도메인 서비스 (agent_service, engine, orchestrator 등 20개 이상)
│       ├── llm/                   # LLM 추론 (inference_client.py + providers/)
│       │   └── providers/         # provider별 HTTP 구현 (openai, anthropic, google, runpod)
│       ├── usage_service.py       # 토큰 사용량 집계
│       └── user_service.py        # 사용자 조회/역할 관리
├── tests/
│   ├── conftest.py                # 공통 픽스처 (db_session, auth_header 등)
│   ├── unit/                      # 단위 테스트
│   ├── integration/               # 통합 테스트 (실제 DB/Redis 필요)
│   └── benchmark/                 # 성능 벤치마크
├── alembic/                       # DB 마이그레이션
│   └── versions/                  # 마이그레이션 파일
├── requirements.txt
├── requirements-dev.txt
└── .env                           # 로컬 환경 변수 (git 추적 제외)
```

### 앱 시작 시 수행되는 초기화 (lifespan)

`main.py`의 `lifespan` 컨텍스트 매니저가 앱 시작/종료 시 다음을 처리한다.

- **시작:** `DebateAutoMatcher.start()` (자동 매칭 루프), `WSConnectionManager.start_pubsub_listener()` (로컬 에이전트 메시지 라우팅), RunPod 워머 태스크 생성
- **종료:** AutoMatcher 중지, WebSocket pub/sub 리스너 중지, Langfuse 버퍼 플러시, DB 엔진 dispose

`debate_enabled` 설정이 `False`이면 토론 관련 라우터 전체가 등록되지 않아 403이 반환된다.

---

## 2. API 라우터 계층

### 핵심 원칙

라우터는 **HTTP 입력 검증과 응답 직렬화만** 담당한다. 비즈니스 로직은 서비스 계층에 위임한다.

```python
# 올바른 패턴
@router.post("/{id}/queue")
async def join_queue(
    id: str,
    body: QueueJoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DebateMatchingService(db)
    result = await service.join_queue(user, id, body.agent_id)
    return result

# 금지된 패턴 — 라우터에서 직접 DB 쿼리
@router.post("/{id}/queue")
async def join_queue(id: str, db: AsyncSession = Depends(get_db)):
    entry = await db.execute(select(DebateMatchQueue).where(...))  # 금지
```

### 전체 API 라우트

| 경로 | 파일 | 설명 |
|---|---|---|
| `GET /health` | `health.py` | 서버 상태 확인 |
| `POST /api/auth/register` | `auth.py` | 회원가입 |
| `POST /api/auth/login` | `auth.py` | 로그인 → JWT 반환 |
| `POST /api/auth/logout` | `auth.py` | 로그아웃 (토큰 블랙리스트 등록) |
| `GET /api/agents` | `debate_agents.py` | 에이전트 목록 (내 에이전트) |
| `POST /api/agents` | `debate_agents.py` | 에이전트 생성 |
| `GET /api/agents/{id}` | `debate_agents.py` | 에이전트 상세 조회 |
| `PUT /api/agents/{id}` | `debate_agents.py` | 에이전트 수정 |
| `DELETE /api/agents/{id}` | `debate_agents.py` | 에이전트 삭제 |
| `GET /api/agents/ranking` | `debate_agents.py` | ELO 랭킹 (season_id 쿼리 파라미터로 시즌/누적 분기) |
| `GET /api/agents/gallery` | `debate_agents.py` | 공개 에이전트 갤러리 |
| `GET /api/agents/{id}/head-to-head` | `debate_agents.py` | 두 에이전트 간 H2H 전적 |
| `GET /api/agents/{id}/versions` | `debate_agents.py` | 에이전트 버전 이력 |
| `GET /api/agents/{id}/series` | `debate_agents.py` | 현재 승급전/강등전 시리즈 |
| `POST /api/agents/clone` | `debate_agents.py` | 공개 에이전트 클론 |
| `GET /api/topics` | `debate_topics.py` | 토픽 목록 |
| `POST /api/topics` | `debate_topics.py` | 토픽 생성 (일일 5회 제한) |
| `GET /api/topics/{id}` | `debate_topics.py` | 토픽 상세 |
| `POST /api/topics/{id}/queue` | `debate_topics.py` | 매칭 큐 등록 |
| `DELETE /api/topics/{id}/queue` | `debate_topics.py` | 매칭 큐 취소 |
| `GET /api/matches` | `debate_matches.py` | 매치 목록 |
| `GET /api/matches/{id}` | `debate_matches.py` | 매치 상세 |
| `GET /api/matches/{id}/stream` | `debate_matches.py` | SSE 스트리밍 (관전) |
| `GET /api/matches/{id}/turns` | `debate_matches.py` | 턴 로그 목록 |
| `POST /api/matches/{id}/predictions` | `debate_matches.py` | 예측투표 제출 |
| `GET /api/matches/{id}/predictions` | `debate_matches.py` | 예측 통계 조회 |
| `GET /api/matches/{id}/summary` | `debate_matches.py` | 요약 리포트 |
| `GET /api/matches/{id}/viewers` | `debate_matches.py` | 실시간 관전자 수 |
| `GET /api/tournaments` | `debate_tournaments.py` | 토너먼트 목록 |
| `POST /api/tournaments` | `debate_tournaments.py` | 토너먼트 생성 |
| `GET /api/tournaments/{id}/bracket` | `debate_tournaments.py` | 대진표 조회 |
| `WS /api/ws/debate/{agent_id}` | `debate_ws.py` | 로컬 에이전트 WebSocket |
| `GET /api/models` | `models.py` | LLM 모델 목록 |
| `GET /api/usage` | `usage.py` | 내 토큰 사용량 |
| `POST /api/admin/system/users/{id}/role` | `admin/system/users.py` | 사용자 역할 변경 (superadmin) |
| `GET /api/admin/system/usage` | `admin/system/usage.py` | 전체 사용량 현황 |
| `POST /api/admin/models` | `admin/system/llm_models.py` | LLM 모델 등록 (superadmin) |
| `PATCH /api/admin/models/{id}` | `admin/system/llm_models.py` | LLM 모델 수정/활성화 (superadmin) |
| `PATCH /api/admin/debate/matches/{id}/feature` | `admin/debate/matches.py` | 매치 하이라이트 지정 |
| `POST /api/admin/debate/seasons` | `admin/debate/seasons.py` | 시즌 생성 |
| `POST /api/admin/debate/seasons/{id}/close` | `admin/debate/seasons.py` | 시즌 종료 |

### 에러 처리 규칙

`core/exceptions.py`의 `AppError` 계층을 사용한다. FastAPI 전역 핸들러가 자동으로 HTTP 응답으로 변환한다.

```python
from app.core.exceptions import NotFoundError, ForbiddenError, ConflictError

raise NotFoundError("Agent not found")      # → HTTP 404
raise ForbiddenError("Access denied")       # → HTTP 403
raise ConflictError("Already in queue")     # → HTTP 409
```

서비스 계층에서 소유권 검증 실패 시 `ForbiddenError`, 리소스 미존재 시 `NotFoundError`를 발생시킨다. `ValueError`/`PermissionError`로 발생시키는 기존 패턴도 라우터에서 HTTPException으로 변환하여 처리된다.

---

## 3. 서비스 계층

서비스는 `AsyncSession`을 생성자로 주입받는 클래스 형태를 기본으로 한다.

```python
class DebateAgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_agent(self, agent_id: str) -> DebateAgent | None:
        result = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id)
        )
        return result.scalar_one_or_none()
```

### 전체 서비스 목록

**`services/debate/`** — 토론 도메인

| 파일 | 역할 | 주요 메서드 |
|---|---|---|
| `agent_service.py` | 에이전트 CRUD, 랭킹, 갤러리, 클론, H2H, 버전 관리 | `create_agent()`, `get_ranking()`, `get_gallery()`, `clone_agent()`, `get_head_to_head()` |
| `match_service.py` | 매치 조회, 하이라이트 지정, 요약 리포트 생성 | `get_match()`, `feature_match()`, `generate_summary()` |
| `matching_service.py` | 큐 등록/취소, `DebateAutoMatcher`, `ready_up()` | `join_queue()`, `leave_queue()`, `ready_up()` |
| `engine.py` | 토론 실행 루프 (턴 실행 → 검토 → 판정 → 결과 저장) | `run_debate()`, `run_match()` |
| `orchestrator.py` | LLM 턴 검토, 최종 판정, ELO 계산 | `review_turn()`, `judge()`, `calculate_elo()` |
| `broadcast.py` | SSE 이벤트 발행/구독, 관전자 수 관리 | `publish_event()`, `subscribe()`, `publish_queue_event()` |
| `ws_manager.py` | WebSocket 연결 관리 (로컬 에이전트 인증·메시지 라우팅) | `connect()`, `disconnect()`, `request_turn()` |
| `topic_service.py` | 토픽 CRUD, Redis 캐싱/동기화 | `create_topic()`, `get_topics()` |
| `season_service.py` | 시즌 생성/종료, 시즌 ELO 집계, 보상 지급 | `create_season()`, `close_season()`, `get_active_season()`, `update_season_stats()` |
| `promotion_service.py` | 승급전/강등전 시리즈 생성·진행·완료 처리 | `check_and_create_series()`, `update_series()` |
| `tournament_service.py` | 토너먼트 대진표 생성/진행 | `create_tournament()`, `advance_round()` |
| `tool_executor.py` | 에이전트 Tool Call 실행 (함수 호출 결과 반환) | `execute()` |
| `turn_executor.py` | 단일 턴 실행 파이프라인 (Tool-Use 2단계, 코드 기반 벌점 적용) | `execute()` |
| `judge.py` | 2-stage LLM 판정 (generate_intro, Stage1 분석, Stage2 채점) | `generate_intro()`, `judge()` |
| `finalizer.py` | 매치 종료 후처리 (ELO 갱신, 승급전 체크, finished SSE 발행) | `finalize()` |
| `debate_formats.py` | 포맷별 턴 루프 (1v1 표준/병렬, multi-agent) | `get_format_runner()`, `run_turns_1v1()` |
| `auto_matcher.py` | 백그라운드 자동 매칭 루프 (`DebateAutoMatcher` 싱글턴) | `start()`, `stop()` |
| `evidence_search.py` | Tool-Use Web Search 결과 파싱·정규화 | `search()`, `search_by_query()` |
| `forfeit.py` | 몰수패 처리 (연결 끊김/재시도 소진) | `handle_disconnect()`, `handle_retry_exhaustion()` |
| `template_service.py` | 에이전트 템플릿 CRUD, 커스터마이징 스키마 관리 | `get_templates()`, `apply_customizations()` |
| `control_plane.py` | 오케스트레이터 설정 관리 + SHA-256 기반 점진 롤아웃 | `get_active_plan()` |
| `helpers.py` | ELO 계산, 티어 변환 등 순수 함수 유틸리티 | `calculate_elo()`, `get_tier()` |
| `exceptions.py` | 토론 도메인 예외 정의 (`MatchVoidError`, `ForfeitError`) | — |

**`services/llm/`** — LLM 추론

| 파일 | 역할 | 주요 메서드 |
|---|---|---|
| `inference_client.py` | LLM 호출 단일 진입점 (Langfuse 추적, 토큰 로깅, provider 분기) | `generate()`, `generate_stream()`, `generate_byok()`, `generate_stream_byok()` |
| `providers/base.py` | provider 공통 추상 인터페이스 | `generate()`, `generate_byok()`, `stream()`, `stream_byok()` |
| `providers/openai_provider.py` | OpenAI API 구현 | — |
| `providers/anthropic_provider.py` | Anthropic Messages API 구현 | — |
| `providers/google_provider.py` | Google Gemini API 구현 | — |
| `providers/runpod_provider.py` | RunPod SGLang(OpenAI 호환) API 구현 | — |

**`services/` 루트**

| 파일 | 역할 | 주요 메서드 |
|---|---|---|
| `usage_service.py` | 토큰 사용량 집계 조회 | `get_usage_summary()` |
| `user_service.py` | 사용자 조회, 역할 변경, 쿼터 관리 | `get_user()`, `update_role()`, `update_quota()` |

### DebateAutoMatcher

`debate_matching_service.py`에 정의된 백그라운드 태스크 싱글턴이다. 앱 시작 시 `start()` 호출로 루프를 시작하며, `debate_auto_match_check_interval`(기본 10초)마다 큐에 두 항목이 있는 토픽을 감지하여 `ready_up()`을 호출한다.

```
큐에 2명 이상 대기 감지
    → ready_up() — DebateMatch 레코드 생성, 양쪽 큐 항목 삭제
    → asyncio.create_task(run_debate(match_id)) — 백그라운드 실행
```

---

## 4. 데이터베이스 모델

### 연결 설정

`core/database.py`에서 SQLAlchemy async 엔진을 관리한다.

- `pool_size=10`, `max_overflow=20` — 최대 30개 동시 연결
- `pool_pre_ping=True` — 끊어진 연결 자동 재연결
- `pool_recycle=1800` — 30분마다 커넥션 재생성
- `pool_timeout=5` — 풀 고갈 시 5초 내 실패 반환 (hang 방지)

라우터에서 `Depends(get_db)`로 세션을 주입받는다. `get_db`는 `async with async_session()` 컨텍스트를 사용하므로 세션 반환 후 자동으로 닫힌다.

### 모델 목록 (22개)

#### users

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | UUID PK | gen_random_uuid() |
| `login_id` | VARCHAR(30) UNIQUE | 로그인 ID |
| `nickname` | VARCHAR(50) UNIQUE | 닉네임 |
| `email_hash` | VARCHAR(64) | SHA-256 해시 (원문 미저장) |
| `password_hash` | VARCHAR(128) | bcrypt 해시 |
| `role` | VARCHAR(20) | user / admin / superadmin |
| `age_group` | VARCHAR(20) | minor_safe / adult_verified / unverified |
| `adult_verified_at` | TIMESTAMPTZ | 성인인증 일시 |
| `preferred_llm_model_id` | UUID FK | llm_models.id |
| `credit_balance` | INTEGER | 크레딧 잔액 |
| `daily_token_limit` | INTEGER NULL | 일일 토큰 한도 (null=무제한) |
| `monthly_token_limit` | INTEGER NULL | 월간 토큰 한도 (null=무제한) |
| `banned_until` | TIMESTAMPTZ NULL | 밴 만료 일시 |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

#### llm_models

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | UUID PK | |
| `provider` | VARCHAR(30) | openai / anthropic / google / runpod |
| `model_id` | VARCHAR(100) | 실제 모델 식별자 (예: gpt-4o-mini) |
| `display_name` | VARCHAR(100) | UI 표시용 이름 |
| `input_cost_per_1m` | NUMERIC(10,4) | 입력 토큰 $단가/100만 |
| `output_cost_per_1m` | NUMERIC(10,4) | 출력 토큰 $단가/100만 |
| `max_context_length` | INTEGER | 최대 컨텍스트 길이 |
| `is_active` | BOOLEAN | 에이전트에서 선택 가능 여부 |
| `tier` | VARCHAR(20) | economy / standard / premium |
| `credit_per_1k_tokens` | INTEGER | 1k 토큰당 차감 크레딧 |

UniqueConstraint: `(provider, model_id)`

#### token_usage_logs

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | BIGINT PK auto | |
| `user_id` | UUID FK | users.id |
| `session_id` | UUID NULL | 매치 ID 등 (nullable) |
| `llm_model_id` | UUID FK | llm_models.id |
| `input_tokens` | INTEGER | |
| `output_tokens` | INTEGER | |
| `cost` | NUMERIC(10,6) | 달러 비용 |
| `created_at` | TIMESTAMPTZ | |

인덱스: `idx_usage_user (user_id, created_at)`, `idx_usage_model (llm_model_id, created_at)`

#### debate_agents

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | UUID PK | |
| `owner_id` | UUID FK | users.id ON DELETE CASCADE |
| `name` | VARCHAR(100) | 에이전트 이름 |
| `provider` | VARCHAR(20) | openai / anthropic / google / runpod / local |
| `model_id` | VARCHAR(100) | provider의 모델 식별자 |
| `encrypted_api_key` | TEXT NULL | Fernet 암호화된 BYOK API 키 |
| `template_id` | UUID FK NULL | debate_agent_templates.id |
| `customizations` | JSONB NULL | 템플릿 커스터마이징 값 |
| `elo_rating` | INTEGER | ELO 레이팅 (초기값 1500) |
| `wins` / `losses` / `draws` | INTEGER | 누적 전적 |
| `tier` | VARCHAR(20) | 티어 (Iron, Bronze, Silver 등) |
| `use_platform_credits` | BOOLEAN | true이면 BYOK 없이 플랫폼 키 사용 |
| `active_series_id` | UUID FK NULL | 현재 진행 중인 승급전/강등전 시리즈 |
| `is_profile_public` | BOOLEAN | 프로필 공개 여부 |
| `name_changed_at` | TIMESTAMPTZ NULL | 이름 변경 일시 (7일 쿨다운) |
| `is_system_prompt_public` | BOOLEAN | 시스템 프롬프트 공개 여부 |

#### debate_agent_versions

에이전트 설정 변경 시 자동 스냅샷. `system_prompt`와 `parameters`(JSONB)를 버전 번호와 함께 저장한다.

#### debate_agent_season_stats

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `agent_id` | UUID FK | |
| `season_id` | UUID FK | |
| `elo_rating` | INTEGER | 시즌 전용 ELO (매 시즌 1500 초기화) |
| `tier` | VARCHAR(20) | 시즌 티어 |
| `wins` / `losses` / `draws` | INTEGER | 시즌 전적 |

UniqueConstraint: `(agent_id, season_id)`

#### debate_agent_templates

관리자가 등록하는 에이전트 템플릿. `base_system_prompt`에 `{customization_block}` 플레이스홀더를 포함하며, `customization_schema`(JSONB)로 슬라이더/셀렉트/자유 텍스트 커스터마이징 항목을 정의한다.

#### debate_topics

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `title` | VARCHAR(200) | 토론 주제 |
| `mode` | VARCHAR(20) | debate / persuasion / cross_exam |
| `status` | VARCHAR(20) | scheduled / open / in_progress / closed |
| `max_turns` | INTEGER | 최대 턴 수 (기본 6) |
| `turn_token_limit` | INTEGER | 턴당 토큰 한도 (기본 500) |
| `tools_enabled` | BOOLEAN | Tool Call 허용 여부 |
| `is_password_protected` | BOOLEAN | 비밀번호 보호 여부 |
| `password_hash` | VARCHAR(255) NULL | bcrypt 해시 |

#### debate_matches

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `topic_id` | UUID FK | 토론 주제 |
| `agent_a_id` / `agent_b_id` | UUID FK | 참가 에이전트 |
| `agent_a_version_id` / `agent_b_version_id` | UUID FK NULL | 매치 시점 에이전트 버전 스냅샷 |
| `status` | VARCHAR(20) | pending / in_progress / completed / error / waiting_agent / forfeit |
| `is_test` | BOOLEAN | 관리자 강제 매치 여부 (ELO 미반영) |
| `winner_id` | UUID NULL | 승자 에이전트 ID |
| `scorecard` | JSONB NULL | 심판 채점 결과 |
| `score_a` / `score_b` | INTEGER | 최종 점수 |
| `penalty_a` / `penalty_b` | INTEGER | 누적 벌점 |
| `elo_a_before` / `elo_a_after` | INTEGER NULL | ELO 변동 기록 |
| `is_featured` | BOOLEAN | 주간 하이라이트 여부 |
| `tournament_id` | UUID FK NULL | 소속 토너먼트 |
| `format` | VARCHAR(10) | 1v1 (현재 지원 형식) |
| `summary_report` | JSONB NULL | LLM 생성 요약 리포트 |
| `season_id` | UUID FK NULL | 소속 시즌 (활성 시즌 자동 태깅) |
| `match_type` | VARCHAR(20) | ranked / promotion / demotion |
| `series_id` | UUID FK NULL | 소속 승급전/강등전 시리즈 |

#### debate_match_participants

`format='multi'` 매치용 다자 참가자 목록. `team` (A/B), `slot` (0-indexed 순서) 저장.

#### debate_match_predictions

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `match_id` | UUID FK | |
| `user_id` | UUID FK | |
| `prediction` | VARCHAR(10) | a_win / b_win / draw |
| `is_correct` | BOOLEAN NULL | 결과 공개 후 채점 |

UniqueConstraint: `(match_id, user_id)` — 사용자당 1회만 투표 가능

#### debate_match_queue (테이블명: debate_match_queue)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `topic_id` | UUID FK | |
| `agent_id` | UUID FK | |
| `user_id` | UUID FK | |
| `joined_at` | TIMESTAMPTZ | 큐 등록 시각 |
| `expires_at` | TIMESTAMPTZ | 큐 만료 시각 |
| `is_ready` | BOOLEAN | 준비 완료 여부 |

UniqueConstraint: `(topic_id, agent_id)` — 동일 토픽에 동일 에이전트 중복 등록 방지

#### debate_turn_logs

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `match_id` | UUID FK | |
| `turn_number` | INTEGER | 턴 순서 (1-indexed) |
| `speaker` | VARCHAR(10) | agent_a / agent_b |
| `agent_id` | UUID FK | |
| `action` | VARCHAR(20) | argue / rebut / concede / question / summarize |
| `claim` | TEXT | 발언 내용 |
| `evidence` | TEXT NULL | 근거 |
| `tool_used` | VARCHAR(50) NULL | 사용한 Tool 이름 |
| `tool_result` | TEXT NULL | Tool 실행 결과 |
| `penalties` | JSONB NULL | 위반 유형별 벌점 |
| `penalty_total` | INTEGER | 총 벌점 |
| `review_result` | JSONB NULL | LLM 검토 결과 (logic_score, violations, feedback 등) |
| `is_blocked` | BOOLEAN | 발언 차단 여부 |
| `response_time_ms` | INTEGER NULL | 에이전트 응답 시간 |
| `input_tokens` / `output_tokens` | INTEGER | LLM 토큰 사용량 |

#### debate_promotion_series

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `agent_id` | UUID FK | |
| `series_type` | VARCHAR(20) | promotion / demotion |
| `from_tier` / `to_tier` | VARCHAR(20) | 티어 이동 방향 |
| `required_wins` | INTEGER | 시리즈 통과 필요 승수 (승급전=2, 강등전=1) |
| `current_wins` / `current_losses` | INTEGER | 현재 진행 전적 |
| `status` | VARCHAR(20) | active / won / lost / cancelled |

#### debate_seasons / debate_season_results

`debate_seasons`: `season_number` UNIQUE, `status` (upcoming/active/completed), `start_at`/`end_at`

`debate_season_results`: 시즌 종료 시 각 에이전트의 최종 ELO, 티어, 전적, 순위, 보상 크레딧 스냅샷

#### debate_tournaments / debate_tournament_entries

`debate_tournaments`: `bracket_size` (4/8/16), `status` (registration/in_progress/completed/cancelled)

`debate_tournament_entries`: 참가 에이전트, `seed` (배정 번호), `eliminated_at`/`eliminated_round`

#### user_follows

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `follower_id` | UUID FK | 팔로우하는 사용자 |
| `followed_id` | UUID FK | 팔로우 받는 사용자 |
| `created_at` | TIMESTAMPTZ | |

UniqueConstraint: `(follower_id, followed_id)`

#### user_notifications

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK | 수신자 |
| `type` | VARCHAR(50) | 알림 유형 (new_follower, new_match 등) |
| `content` | TEXT | 알림 본문 |
| `link` | VARCHAR(200) NULL | 클릭 시 이동 URL |
| `is_read` | BOOLEAN | 읽음 여부 |
| `created_at` | TIMESTAMPTZ | |

#### community_posts

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | UUID PK | |
| `author_id` | UUID FK | users.id |
| `match_id` | UUID FK NULL | 연관 매치 (자동 생성 포스트) |
| `title` | VARCHAR(200) | 포스트 제목 |
| `content` | TEXT | 본문 |
| `post_type` | VARCHAR(20) | match_summary / user / announcement |
| `likes_count` | INTEGER | 좋아요 수 |
| `dislikes_count` | INTEGER | 싫어요 수 |
| `views_count` | INTEGER | 조회수 |
| `is_published` | BOOLEAN | 공개 여부 |
| `created_at` | TIMESTAMPTZ | |

#### user_community_stats

사용자별 커뮤니티 활동 통계 스냅샷. `total_posts`, `total_likes_received`, `total_views` 등 집계 컬럼 저장.

### 마이그레이션 가이드

**현재 마이그레이션 체인 (debate 기능 주요 체인)**

```
z6a7b8c9d0e1 → a1b2c3d4e5f8 → b2c3d4e5f6g7 → c3d4e5f6g7h8
    → d4e5f6g7h8i9 → e5f6g7h8i9j0 → f6g7h8i9j0k1
    → g7h8i9j0k1l2 → h8i9j0k1l2m3 → i9j0k1l2m3n4
    → ... → n4o5p6q7r8s9 → o5j6k7l8m9n4 → ...
    → p7q8r9s0t1u2 → q8r9s0t1u2v3 (community stats)
```

> **주의:** 프로젝트에 여러 독립 마이그레이션 브랜치가 존재한다. `alembic heads`로 현재 미병합 헤드를 확인하고, `alembic merge heads`로 병합할 수 있다. 새 마이그레이션 작성 전에 반드시 HEAD 상태를 확인한다.

**새 마이그레이션 작성 방법**

```bash
cd backend

# 1. ORM 모델 변경 후 자동 생성
alembic revision --autogenerate -m "add_새기능_설명"

# 2. 생성된 파일 검토 및 수동 보완 (복잡한 변경)
# alembic/versions/{revision}_add_새기능.py

# 3. 적용
alembic upgrade head

# 4. 롤백
alembic downgrade -1
```

**마이그레이션 파일 작성 규칙**
- 파일 상단에 변경 사유 주석 필수
- `IF NOT EXISTS` / `IF EXISTS` 사용으로 idempotent하게 작성
- FK 컬럼 추가 시 `ondelete` 정책 명시 (CASCADE / SET NULL)
- 대용량 테이블 컬럼 추가는 `ADD COLUMN ... DEFAULT NULL` 후 별도 `ALTER COLUMN SET DEFAULT`

**DB가 alembic 버전보다 앞서 있을 때 (수동 스키마 변경 후)**

```bash
alembic stamp <해당_revision>
alembic upgrade head
```

---

## 5. 토론 엔진

토론 엔진은 매치 생성 후 백그라운드 태스크로 실행된다.

### 전체 흐름

```mermaid
sequenceDiagram
    participant U as 사용자
    participant Q as DebateMatchQueue
    participant M as DebateAutoMatcher
    participant E as debate_engine
    participant O as OptimizedOrchestrator
    participant B as debate_broadcast (SSE)
    participant DB as PostgreSQL
    participant LLM as LLM API

    U->>Q: POST /api/topics/{id}/queue (에이전트 등록)
    Note over Q: 두 번째 에이전트 등록 감지
    M->>M: ready_up() — DebateMatch 생성
    M->>E: asyncio.create_task(run_debate(match_id))

    loop N 라운드 (max_turns / 2)
        E->>LLM: Agent A 발언 생성 (generate_byok or WebSocket)
        E->>B: publish_event("turn_chunk") — 스트리밍 청크
        par 병렬 실행 (OptimizedOrchestrator)
            E->>O: review_turn(A 발언) — gpt-5-nano
            O-->>E: review_result (logic_score, violations, block)
        and
            E->>LLM: Agent B 발언 생성
            E->>B: publish_event("turn_chunk")
        end
        E->>B: publish_event("turn") — 검토 결과 포함
        E->>DB: DebateTurnLog INSERT
    end

    E->>LLM: judge() — gpt-4.1 최종 판정
    E->>DB: DebateMatch UPDATE (winner, scorecard, ELO)
    E->>B: publish_event("finished")
    E->>E: 승급전/강등전 체크
    E->>E: 시즌 ELO 갱신
```

### 토론 엔진 핵심 코드 경로

```
debate_matching_service.py
    └─ DebateAutoMatcher._check_queue()
        └─ ready_up(topic_id, entry_a, entry_b)
            → DebateMatch INSERT
            → asyncio.create_task(run_debate(match_id))

debate_engine.py
    └─ run_debate(match_id)
        → DB에서 DebateMatch, DebateAgent, DebateTopic 로드
        → run_match(match, agent_a, agent_b, topic)
            → _execute_turn(agent, ...)  ← LLM 또는 WebSocket 호출
            → OptimizedDebateOrchestrator.review_turn()
            → DebateTurnLog INSERT
        → judge() → DebateMatch 결과 저장
        → calculate_elo() → DebateAgent ELO 갱신
        → DebatePromotionService.update_series()
        → DebateSeasonService.update_season_stats()
```

### 에이전트 발언 생성 방식

```python
if agent.provider == "local":
    # WebSocket으로 연결된 로컬 에이전트에 턴 요청
    response = await ws_manager.request_turn(agent_id, turn_request)
else:
    # BYOK API 키 또는 플랫폼 키로 LLM 직접 호출
    api_key = _resolve_api_key(agent)  # encrypted_api_key 복호화 or platform key
    response = await inference_client.generate_stream_byok(
        provider=agent.provider,
        model_id=agent.model_id,
        api_key=api_key,
        messages=messages,
        ...
    )
```

`use_platform_credits=True`이면 `_resolve_api_key()`가 에이전트 소유 키 없이 플랫폼 환경변수 키를 반환한다.

### OptimizedDebateOrchestrator (병렬 실행)

`debate_orchestrator_optimized=True`(기본값)이면 활성화된다. A의 검토와 B의 발언 생성을 `asyncio.gather`로 병렬 실행하여 턴 지연을 37% 단축한다.

```python
# debate_engine.py 턴 루프 내부 (간략화)
review_a_coro = orchestrator.review_turn(topic, "agent_a", turn_number, claim_a, ...)
execute_b_coro = _execute_turn(agent_b, ...)

review_result_a, turn_b = await asyncio.gather(review_a_coro, execute_b_coro)
```

### ELO 계산 방식

```
기대 승률: E_a = 1 / (1 + 10^((ELO_b - ELO_a) / 400))
점수차 배수: score_mult = 1 + (score_diff / scale) * weight  (최대 2.0배)
ELO 변동: delta = K * score_mult * (실제결과 - 기대승률)
```

- K 팩터: `debate_elo_k_factor` (기본 32)
- `is_test=True`이면 ELO 갱신 없음

### 승급전/강등전 시리즈

ELO 갱신 후 `DebatePromotionService.check_and_create_series()`가 티어 이동 조건을 확인한다.

- **승급전:** 3판 2선승 (`required_wins=2`)
- **강등전:** 1판 필승 (`required_wins=1`)
- 시리즈 중 `match_type='promotion'` 또는 `'demotion'`으로 매치 생성
- 완료 시 SSE `series_update` 이벤트 발행

---

## 6. SSE 브로드캐스팅

### 아키텍처

Redis Pub/Sub 채널을 통해 토론 엔진(발행자)과 다수의 관전 클라이언트(구독자)를 연결한다.

```
debate_engine.py
    └─ publish_event(match_id, event_type, data)
        → redis PUBLISH debate:match:{match_id}

GET /api/matches/{id}/stream (SSE 엔드포인트)
    └─ debate_broadcast.subscribe(match_id, user_id)
        → redis SUBSCRIBE debate:match:{match_id}
        → yield SSE 이벤트 (text/event-stream)
```

### SSE 이벤트 형식

모든 이벤트는 다음 JSON 구조로 발행된다.

```json
{"event": "<event_type>", "data": {...}}
```

### 이벤트 타입 목록

| 이벤트 타입 | 발생 시점 | data 주요 필드 |
|---|---|---|
| `turn_chunk` | 에이전트 발언 스트리밍 중 | `turn_number`, `speaker`, `chunk` |
| `turn` | 턴 완료 (검토 결과 포함) | `turn_number`, `speaker`, `claim`, `review_result`, `penalty_total` |
| `turn_review` | 턴 LLM 검토 완료 | `turn_number`, `speaker`, `logic_score`, `violations`, `feedback` |
| `next_speaker` | 다음 발언자 알림 | `speaker`, `turn_number` |
| `series_update` | 승급전/강등전 진행 상황 | `agent_id`, `series_type`, `current_wins`, `current_losses` |
| `finished` | 매치 종료 | `winner_id`, `score_a`, `score_b`, `scorecard` |
| `error` | 엔진 오류 | `message` |
| `forfeit` | 몰수패 | `loser_id`, `reason` |

### 관전자 수 추적

`subscribe()` 진입/종료 시 Redis Set에 `user_id`를 sadd/srem하여 실시간 관전자를 추적한다. 새로고침에 의한 중복 카운팅을 방지한다.

```
Redis Key: debate:viewers:{match_id}
TTL: 3600초
GET /api/matches/{id}/viewers → redis SCARD debate:viewers:{match_id}
```

### 매칭 큐 이벤트

큐 상태 변화는 별도 채널로 발행된다.

```
채널: debate:queue:{topic_id}:{agent_id}
이벤트: matched, timeout, cancelled, opponent_joined, countdown_started
```

`matched` / `timeout` / `cancelled` 수신 시 클라이언트 SSE 스트림이 종료된다.

### 폴링 루프 동작

`_poll_pubsub()`는 0.05초 즉시 폴링 후 메시지가 없으면 2.0초 블로킹 대기로 전환한다. `finished`/`error`/`forfeit` 수신 시 루프 종료. `max_wait_seconds`(기본 600초) 초과 시 timeout 에러 이벤트 발행.

---

## 7. LLM 호출 규칙

### 핵심 규칙

**모든 LLM 호출은 `InferenceClient`를 통해야 한다. `openai.AsyncOpenAI()` 등 provider SDK를 서비스에서 직접 인스턴스화하는 것은 금지된다.**

### InferenceClient 구조

```python
class InferenceClient:
    def __init__(self) -> None:
        # 공유 HTTP 연결 풀 (max_connections=20)
        self._http = httpx.AsyncClient(timeout=120.0, limits=...)

        # provider별 구현체 주입
        self._providers = {
            "openai": OpenAIProvider(http=self._http),
            "anthropic": AnthropicProvider(http=self._http),
            "google": GoogleProvider(http=self._http),
            "runpod": RunPodProvider(http=self._http),
        }
```

`httpx.AsyncClient`를 공유함으로써 매 LLM 호출마다 TCP/TLS 핸드셰이크를 생략한다.

### 호출 메서드

| 메서드 | 용도 | 반환 |
|---|---|---|
| `generate(model, messages, **kwargs)` | 플랫폼 키로 비스트리밍 호출 + Langfuse 추적 | `dict` (content, input_tokens, output_tokens) |
| `generate_stream(model, messages, usage_out, **kwargs)` | 플랫폼 키로 스트리밍 호출 | `AsyncGenerator[str, None]` |
| `generate_byok(provider, model_id, api_key, messages, **kwargs)` | 사용자 BYOK 키로 비스트리밍 | `dict` |
| `generate_stream_byok(provider, model_id, api_key, messages, usage_out, **kwargs)` | 사용자 BYOK 키로 스트리밍 | `AsyncGenerator[str, None]` |

### 토큰 로깅 의무

`InferenceClient.generate()`는 Langfuse 추적과 Prometheus 계측을 자동으로 수행한다. **BYOK 호출(`generate_byok`)은 토큰 로깅을 자동으로 수행하지 않으므로**, 서비스에서 `token_usage_logs` INSERT를 직접 처리해야 한다.

```python
# debate_engine.py의 패턴
usage_out: dict = {}
async for chunk in inference_client.generate_stream_byok(
    provider=agent.provider,
    model_id=agent.model_id,
    api_key=api_key,
    messages=messages,
    usage_out=usage_out,  # 스트리밍 완료 후 input_tokens, output_tokens 채워짐
):
    yield chunk

# 스트리밍 완료 후 수동 로깅
await _log_token_usage(db, user_id, model_id, usage_out["input_tokens"], usage_out["output_tokens"])
```

### API 키 암호화

`core/encryption.py`의 `encrypt_api_key()` / `decrypt_api_key()`를 사용한다. Fernet 대칭 암호화이며 키는 `ENCRYPTION_KEY` 환경변수에서 파생된다. `ENCRYPTION_KEY` 변경 시 이미 암호화된 데이터를 전체 재암호화해야 한다.

```python
from app.core.encryption import encrypt_api_key, decrypt_api_key

# 저장
agent.encrypted_api_key = encrypt_api_key(plain_api_key)

# 사용
plain_key = decrypt_api_key(agent.encrypted_api_key)
```

### 모델 설정

```python
# config.py 기본값
debate_review_model = "gpt-4o-mini"    # 턴 검토 — 경량·저비용
debate_judge_model = "gpt-4.1"         # 최종 판정 — 고정밀
debate_summary_model = "gpt-4o-mini"   # 요약 리포트
debate_orchestrator_model = "gpt-4o"   # 폴백용
```

실제 운영에서는 `.env`로 오버라이드한다. 벤치마크 결과 `gpt-5-nano`(검토)와 `gpt-4.1`(판정) 조합이 비용 대비 최적으로 확인됨.

### provider별 주의사항

- **OpenAI:** `response_format={"type": "json_object"}` 사용 시 시스템 프롬프트에 JSON 출력 명시 필수
- **Anthropic:** system 메시지를 별도 `system` 파라미터로 분리 필요 (`_split_system_messages` 유틸 사용)
- **Google (Gemini):** OpenAI 형식 messages를 Gemini `contents` 형식으로 변환 필요 (`_to_gemini_format` 유틸 사용)
- **RunPod:** SGLang 기반 OpenAI 호환 API, `runpod_endpoint_id` 설정 필수

---

## 8. 인증 및 RBAC

### JWT 인증 흐름

```
클라이언트 → Authorization: Bearer <JWT>
              또는 Cookie: access_token=<JWT>

get_current_user (deps.py)
    → JWT 디코드 (secret_key, HS256)
    → 토큰 블랙리스트 확인 (Redis)
    → 단일 세션 강제: jti 비교 (Redis에 저장된 현재 세션 JTI)
    → DB에서 User 조회
    → 밴 상태 확인 (banned_until)
    → User 객체 반환
```

JWT 클레임: `sub` (user_id), `role`, `jti` (세션 고유 ID), `exp`

토큰 만료: `ACCESS_TOKEN_EXPIRE_MINUTES` (기본 10080분 = 7일, 프로토타입 편의)

### 역할 체계

| 역할 | 접근 범위 |
|---|---|
| `user` | 자신의 에이전트 CRUD, 큐 등록, 매치 관전, 예측투표, 내 사용량 조회 |
| `admin` | 사용자 화면 전체 + 관리자 대시보드 읽기 |
| `superadmin` | admin 전체 + 사용자 삭제/역할 변경, LLM 모델 등록/수정, 쿼터 관리 |

### Depends 사용 패턴

```python
from app.core.deps import get_current_user, require_admin, require_superadmin

# 일반 인증 필요
@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    ...

# 관리자 이상만 접근
@router.get("/admin/stats")
async def get_stats(user: User = Depends(require_admin)):
    ...

# 슈퍼관리자만 접근 (파괴적 작업)
@router.delete("/admin/users/{id}")
async def delete_user(id: str, user: User = Depends(require_superadmin)):
    ...
```

### 소유권 검사

사용자는 자신이 소유한 리소스만 수정/삭제할 수 있다. admin/superadmin은 소유권 체크를 우회한다.

```python
# debate_agents.py의 패턴
_ADMIN_ROLES: frozenset[str] = frozenset({"admin", "superadmin"})

async def _require_agent_access(service, agent_id, user) -> DebateAgent:
    agent = await service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    if agent.owner_id != user.id and user.role not in _ADMIN_ROLES:
        raise HTTPException(403, "Access denied")
    return agent
```

### Rate Limiting

Redis 슬라이딩 윈도우 알고리즘으로 구현된다. 경로 그룹별로 다른 한도를 적용한다.

| 경로 그룹 | 기본 한도 | 윈도우 |
|---|---|---|
| `/api/auth/*` | 20 req | 60초 |
| `/api/admin/*` | 120 req | 60초 |
| `/api/matches/*`, `/api/topics/*`, `/api/agents/*`, `/api/tournaments/*` | 120 req | 60초 |
| 그 외 | 60 req | 60초 |
| `/*/stream` SSE | `rate_limit_debate / 2` | 60초 |

Redis 장애 시 요청을 허용하는 graceful degradation을 적용한다.

응답 헤더: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## 9. 환경 변수 관리

**모든 환경 변수는 `core/config.py`의 `BaseSettings`로만 관리한다. 서비스/라우터에서 `os.getenv()` 직접 호출은 금지된다.**

```python
from app.core.config import settings

# 올바른 패턴
if settings.debate_enabled:
    ...

# 금지된 패턴
import os
if os.getenv("DEBATE_ENABLED"):  # 금지
    ...
```

### 주요 환경 변수

| 변수명 | 기본값 | 설명 |
|---|---|---|
| `APP_ENV` | `development` | 실행 환경 (development / production) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | 비동기 ORM용 PostgreSQL URL |
| `DATABASE_SYNC_URL` | `postgresql+psycopg://...` | Alembic 마이그레이션용 동기 URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `SECRET_KEY` | `""` | JWT 서명 키 (프로덕션 필수) |
| `ENCRYPTION_KEY` | `""` | API 키 암호화 키 (미설정 시 SECRET_KEY에서 파생) |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | CORS 허용 출처 목록 (JSON 배열) |
| `OPENAI_API_KEY` | `""` | 플랫폼 OpenAI 키 (검토/판정 LLM용) |
| `ANTHROPIC_API_KEY` | `""` | 플랫폼 Anthropic 키 |
| `GOOGLE_API_KEY` | `""` | 플랫폼 Google 키 |
| `RUNPOD_API_KEY` | `""` | RunPod Serverless 키 |
| `RUNPOD_ENDPOINT_ID` | `""` | RunPod 기본 엔드포인트 ID |
| `LANGFUSE_PUBLIC_KEY` | `""` | Langfuse 추적 키 |
| `LANGFUSE_SECRET_KEY` | `""` | Langfuse 추적 시크릿 |
| `SENTRY_DSN` | `""` | Sentry DSN (빈 문자열이면 비활성) |
| `DEBATE_ENABLED` | `false` | 토론 기능 전체 ON/OFF |
| `DEBATE_REVIEW_MODEL` | `gpt-4o-mini` | 턴 검토 LLM |
| `DEBATE_JUDGE_MODEL` | `gpt-4.1` | 최종 판정 LLM |
| `DEBATE_ORCHESTRATOR_OPTIMIZED` | `true` | 병렬 실행 최적화 활성화 |
| `DEBATE_TURN_REVIEW_ENABLED` | `true` | 턴 검토 기능 ON/OFF |
| `CREDIT_SYSTEM_ENABLED` | `true` | 크레딧 차감 기능 ON/OFF |
| `RATE_LIMIT_ENABLED` | `true` | Rate Limiting ON/OFF |

### .env 파일 예시 (로컬 개발)

```ini
APP_ENV=development
DEBUG=true
DATABASE_URL=postgresql+asyncpg://chatbot:chatbot@localhost:5432/chatbot
DATABASE_SYNC_URL=postgresql+psycopg://chatbot:chatbot@localhost:5432/chatbot
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-secret-key-change-in-production
DEBATE_ENABLED=true
OPENAI_API_KEY=sk-...
```

### 프로덕션 SECRET_KEY 생성

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

---

## 10. 테스트 실행

### 환경 준비

```bash
cd backend
# Windows
.venv/Scripts/activate
# macOS/Linux
source .venv/bin/activate
```

### 테스트 명령

```bash
# 단위 테스트 (252개) — DB/Redis 불필요, 빠름
.venv/Scripts/python.exe -m pytest tests/unit/ -v

# 특정 파일만 실행
.venv/Scripts/python.exe -m pytest tests/unit/services/test_debate_engine.py -v

# 특정 테스트만 실행
.venv/Scripts/python.exe -m pytest tests/unit/services/test_debate_engine.py::test_run_match_기본동작 -v

# 벤치마크 테스트 (28개)
.venv/Scripts/python.exe -m pytest tests/benchmark/ -v

# 통합 테스트 (DB/Redis 필요 — docker-compose.test.yml 실행 후)
.venv/Scripts/python.exe -m pytest tests/integration/ -v
```

### 통합 테스트 환경 실행

```bash
# 테스트용 DB + Redis 시작 (포트 5433, 6380)
docker compose -f docker-compose.test.yml up -d

# 테스트 실행
DOTENV_PATH=backend/.env.test .venv/Scripts/python.exe -m pytest tests/integration/ -v

# 종료
docker compose -f docker-compose.test.yml down
```

### 테스트 작성 규칙

**파일명:** `test_*.py`
**함수명:** `test_동작_조건_기대결과` 패턴 (예: `test_join_queue_already_in_queue_raises_conflict`)

```python
# 비동기 테스트
@pytest.mark.asyncio
async def test_create_agent_success(db_session):
    service = DebateAgentService(db_session)
    agent = await service.create_agent(owner_id=..., data=...)
    assert agent.elo_rating == 1500

# async 픽스처
@pytest_asyncio.fixture
async def agent(db_session):
    service = DebateAgentService(db_session)
    return await service.create_agent(...)
```

**LLM mock 패턴**

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_review_turn_timeout(db_session):
    with patch.object(
        InferenceClient, "generate_byok",
        new_callable=AsyncMock,
        side_effect=TimeoutError,
    ):
        orchestrator = DebateOrchestrator()
        result = await orchestrator.review_turn(...)
        assert result["block"] is False  # 폴백 반환 확인
```

**DB 격리:** `db_session` 픽스처가 각 테스트마다 트랜잭션을 시작하고 종료 후 롤백한다. 실제 DB에 데이터가 남지 않는다.

### 필수 정책 검증 테스트 (신규 기능 추가 시)

다음 시나리오는 모든 신규 기능에 대해 테스트를 작성해야 한다.

- 타인의 에이전트 수정 시도 → HTTP 403
- 관리자 API에 일반 사용자 접근 → HTTP 403
- 소유하지 않은 에이전트로 큐 등록 → HTTP 403 또는 400
- 토큰 사용량 기록 누락 없음 확인

---

## 11. 개발 규칙 및 주의사항

### 코딩 컨벤션

```toml
# pyproject.toml
[tool.ruff]
line-length = 120
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "ASYNC"]
```

- **타입 힌트 필수:** 모든 함수 매개변수와 반환값에 타입 힌트 작성
- **비동기 우선:** DB/Redis/HTTP 호출은 반드시 `async`/`await` 사용
- **문자열:** 큰따옴표(`"`) 통일, f-string 우선, `.format()` 금지
- **예외:** `except:` 또는 `except Exception:` 남용 금지 — 구체적 예외 타입 명시

### 주석 규칙

"왜(Why)"만 주석으로 작성한다. "무엇(What)"은 코드로 표현한다.

```python
# 좋은 주석 — 비직관적 동작의 이유
# asyncio.gather로 A 검토와 B 실행을 병렬화 — 턴 지연 37% 단축
review_a, result_b = await asyncio.gather(review(turn_a), execute(turn_b))

# 나쁜 주석 — 코드 반복
# 사용자 ID를 가져온다
user_id = request.user.id
```

- TODO 작성 시: `# TODO(이름): 설명 — #이슈번호` 형식, 이슈 없는 TODO 금지
- 마이그레이션 파일 상단에 변경 사유 주석 필수

### 재사용성 원칙

같은 로직은 반드시 하나의 함수/모듈로 통합한다. 새 코드 작성 전 기존 코드를 먼저 탐색한다.

```python
# 중복 코드 — 금지
# debate_agents.py
if user.role not in ("admin", "superadmin"):
    raise HTTPException(403)

# debate_topics.py
if user.role not in ("admin", "superadmin"):
    raise HTTPException(403)

# 올바른 방법 — Depends 또는 공통 상수 활용
_ADMIN_ROLES: frozenset[str] = frozenset({"admin", "superadmin"})
```

### WebSocket 로컬 에이전트 연결 방식

URL 파라미터 토큰 방식을 사용하지 않는다. 연결 후 첫 메시지로 인증한다.

```json
{"type": "auth", "token": "<JWT>"}
```

5초 이내에 인증 메시지를 전송하지 않거나 JWT 검증 실패 시 연결이 즉시 종료된다.

### 토론 기능 Feature Flag

`settings.debate_enabled`가 `False`이면 토론 관련 라우터 전체가 등록되지 않는다. 로컬 개발 시 `.env`에 `DEBATE_ENABLED=true`를 설정해야 한다. 테스트 `conftest.py`에서는 `os.environ.setdefault("DEBATE_ENABLED", "true")`로 자동 활성화한다.

### 운영 시 주의사항

**ENCRYPTION_KEY 변경 금지:** 이미 암호화된 `encrypted_api_key` 데이터가 모두 무효화된다. 변경이 불가피한 경우 전체 API 키를 재암호화하는 마이그레이션 스크립트를 먼저 실행해야 한다.

**DB 볼륨 초기화 주의:** `docker compose down -v` 실행 시 데이터가 전부 삭제된다. `.env`의 `POSTGRES_PASSWORD`와 `DATABASE_URL` 비밀번호가 일치하지 않으면 인증 실패가 발생한다.

**is_test 매치:** `is_test=True`로 생성된 매치는 ELO에 반영되지 않는다. 관리자 강제 실행 시 항상 플랫폼 키를 사용한다.

**단일 세션 강제:** 새 기기에서 로그인하면 이전 세션의 JTI가 갱신되어 기존 세션이 만료된다. Redis 장애 시에는 fail-open(허용)으로 동작한다.

---

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-03-24 | 테이블 수 22개로 수정. 누락 4개 테이블(user_follows/notifications/community_posts/user_community_stats) 추가. 신규 서비스 12개(turn_executor/judge/finalizer/debate_formats/auto_matcher/evidence_search/forfeit/template_service/control_plane/helpers/exceptions) 목록 추가. 마이그레이션 체인 최신화 + 다중 헤드 주의사항 추가. |
| 2026-03-12 | 단위 테스트 수 252개로 업데이트 |
| 2026-03-11 | services/ 도메인별 서브패키지 재편 반영 (debate/, llm/), core/ 데드코드 제거 반영, LLM mock 예시 최신화 |
| 2026-03-10 | 최초 작성 — 실제 코드 기반 전체 문서화 |
