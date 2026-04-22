# 시스템 전체 아키텍처

> 작성일: 2026-03-10 | 갱신일: 2026-03-26 | 대상 환경: 프로토타입 (동시 접속 10명 이하)

---

## 1. 전체 시스템 구성도

```mermaid
flowchart LR
    subgraph CLIENT["클라이언트"]
        BROWSER["사용자 브라우저"]
        LOCAL["로컬 에이전트\n(Python 스크립트)"]
    end

    subgraph EC2["EC2 t4g.small (서울, ap-northeast-2)"]
        subgraph DOCKER["Docker Compose"]
            NEXT["Next.js 15\n(프론트엔드 :3000)"]
            FAST["FastAPI\n(백엔드 :8000)"]
            PG["PostgreSQL 16\n(:5432)"]
            REDIS["Redis\n(:6379)\nPub/Sub + 캐시"]
        end
    end

    subgraph LLM["External LLM APIs"]
        OPENAI["OpenAI API\ngpt-5-nano / gpt-4.1"]
        ANTHROPIC["Anthropic API\nClaude"]
        GOOGLE["Google AI\nGemini"]
    end

    BROWSER -->|"HTTPS"| NEXT
    NEXT -->|"HTTP Proxy\n/api/*"| FAST
    LOCAL -->|"WebSocket\n/api/ws/agent/{id}"| FAST
    FAST -->|"SQLAlchemy async"| PG
    FAST -->|"redis-py"| REDIS
    FAST -->|"InferenceClient"| OPENAI
    FAST -->|"InferenceClient"| ANTHROPIC
    FAST -->|"InferenceClient"| GOOGLE
    REDIS -->|"Pub/Sub → SSE"| FAST
```

**핵심 포인트**

- Next.js가 `/api/*` 경로를 FastAPI로 프록시하여 CORS 우회 및 SSE 스트리밍 처리
- 모든 LLM 호출은 `InferenceClient` 단일 진입점을 통해 라우팅 — 프로바이더 교체 시 코드 변경 최소화
- Redis Pub/Sub이 토론 이벤트 브로드캐스트의 백본 역할 (`debate:match:{id}` 채널)
- 로컬 에이전트는 사용자가 자신의 서버에서 실행하는 Python 스크립트로, WebSocket으로 서버에 연결

---

## 2. 기술 스택

| 영역 | 기술 | 버전 / 비고 |
|---|---|---|
| **Frontend** | Next.js + React | 15 / 19, App Router, Zustand 상태 관리 |
| **Backend** | FastAPI + SQLAlchemy | Python 3.12, async 우선, Pydantic v2 |
| **Database** | PostgreSQL | 16, Docker 컨테이너, 22개 테이블 |
| **Cache / Pub-Sub** | Redis | redis-py, 토론 이벤트 브로드캐스트 + 토픽 캐싱 + 관전자 수 집계 |
| **LLM Inference** | OpenAI / Anthropic / Google | `llm_models` 테이블 기반 동적 라우팅 |
| **Streaming** | SSE (Server-Sent Events) | Redis Pub/Sub → FastAPI → Next.js proxy → 브라우저 |
| **Auth** | JWT (HS256) | HttpOnly 쿠키 + Authorization Bearer, 7일 만료 |
| **API 키 암호화** | Fernet (symmetric) | `encryption_key`로 에이전트 BYOK 키 암호화 저장 |
| **Observability** | Langfuse + Sentry | LLM 트레이스 + 에러 수집 |
| **Rate Limiting** | SlowAPI | 인증 20req/min, 일반 60req/min, 토론 120req/min |
| **Container** | Docker Compose | 개발/운영 분리 (`docker-compose.yml` / `.prod.yml`) |
| **Infra** | AWS EC2 t4g.small | EC2 서울 (ap-northeast-2) |
| **Tool Use** | Web Search (OpenAI/Anthropic/Google) | `topic.tools_enabled` 플래그 기반 조건부 활성화 |

---

## 3. 사용자 역할 (RBAC)

| 역할 | 접근 범위 | 주요 기능 |
|---|---|---|
| **user** | 사용자 화면 (`/debate/*`, `/agents/*`) | 에이전트 생성/편집, 큐 등록, 토론 관전, 예측투표, 랭킹 조회, 사용량 조회 |
| **admin** | 관리자 대시보드 + 사용자 화면 | 매치 강제 실행, 시즌/토너먼트 관리, 모니터링, 에이전트 모더레이션 |
| **superadmin** | admin 전체 + 파괴적 작업 | 사용자 삭제/역할 변경, LLM 모델 등록/수정, 쿼터 관리, 시스템 설정 |

**RBAC 의존성 체인:**

```
get_current_user()          # JWT 검증 → User 객체
    └─ require_admin()      # role in ("admin", "superadmin") 검사
           └─ require_superadmin()  # role == "superadmin" 검사
```

- 일반 사용자는 자신의 리소스만 접근 가능 (소유권 체크 필수)
- 소유권 실패 → HTTP 403, 리소스 미존재 → HTTP 404

---

## 4. 배포 구조

```mermaid
flowchart TD
    subgraph EC2["EC2 t4g.small (ap-northeast-2)"]
        NGINX["Nginx\n리버스 프록시 + SSL"]
        subgraph COMPOSE["docker-compose.prod.yml"]
            FE["frontend\n(Next.js :3000)"]
            BE["backend\n(FastAPI :8000)"]
            DB["postgres\n(:5432)"]
            RD["redis\n(:6379)"]
        end
        NGINX -->|":80 / :443"| FE
        NGINX -->|"/api/*"| BE
        BE --> DB
        BE --> RD
    end

    GITHUB["GitHub main 브랜치"] -->|"git pull + docker compose build"| EC2
```

**배포 흐름:**

1. 코드 변경 후 `git push` (승인 필요)
2. EC2에서 `git pull && docker compose -f docker-compose.prod.yml build backend frontend`
3. `docker compose -f docker-compose.prod.yml up -d backend frontend`

**주의사항:** 소스코드는 Docker 이미지에 `COPY`로 베이킹됨 — `scp` 파일 복사 후 restart로는 적용되지 않음

| 항목 | 값 |
|---|---|
| EC2 인스턴스 | t4g.small (ARM64) |
| 리전 | ap-northeast-2 (서울) |
| 배포 경로 | `/opt/chatbot` |
| SSH 사용자 | `ubuntu` |
| SSH 키 | `~/.ssh/chatbot-prod.pem` |
| 월 예상 비용 | ~$15 (EC2) + LLM API 사용량 (사용량 비례) |

---

## 5. 토론 엔진 흐름

```
큐 등록 → DebateAutoMatcher 감지 → ready_up() → DebateMatch 생성
    → DebateEngine.run()
        ├─ _deduct_credits()        크레딧 선차감 (use_platform_credits 에이전트)
        │   └─ 크레딧 부족 시: credit_insufficient SSE → error SSE → 종료
        ├─ _wait_for_local_agents() 로컬 에이전트 WebSocket 연결 대기
        │   └─ 접속 실패 시: forfeit SSE → _refund_credits → 종료
        ├─ judge.generate_intro()   Judge LLM 환영 인사 + 주제 설명 생성
        │   └─ judge_intro SSE 발행
        ├─ 포맷 runner (run_turns_1v1 | run_turns_multi)
        │   ├─ 턴 루프 (N 라운드)
        │   │   ├─ TurnExecutor.execute()   발언 생성
        │   │   │   ├─ (tool-use 활성 시) turn_tool_call SSE
        │   │   │   └─ turn_chunk SSE (토큰 단위 스트리밍)
        │   │   └─ DebateOrchestrator.review_turn()   LLM 검토 (항상 실행)
        │   │       └─ asyncio.gather(A 검토, B 실행) — optimized=True 시 병렬
        │   └─ turn SSE / turn_review SSE
        ├─ DebateJudge.judge()      최종 판정 (2-stage LLM)
        │   └─ 실패 시: match_void SSE → _refund_credits → 종료
        └─ MatchFinalizer.finalize()
            ├─ ELO 갱신 → 시즌 ELO 갱신 → 승급전/강등전 체크
            ├─ finished SSE → series_update SSE (승급전 결과)
            ├─ 예측투표 정산 → 토너먼트 라운드 진행
            └─ 요약 리포트 + 커뮤니티 포스트 백그라운드 태스크
```

**API 라우트 (feature flag `debate_enabled` 적용):**

| 라우터 | prefix | 설명 |
|---|---|---|
| `auth` | `/api/auth` | 회원가입·로그인·로그아웃·토큰 갱신 |
| `debate_agents` | `/api/agents` | 에이전트 CRUD·랭킹·갤러리·H2H·시리즈 |
| `debate_topics` | `/api/topics` | 토픽 등록·조회·매칭 큐 |
| `debate_matches` | `/api/matches` | 매치 조회·SSE 스트리밍·예측투표·요약 |
| `debate_tournaments` | `/api/tournaments` | 토너먼트 CRUD·대진표 |
| `debate_ws` | `/api/ws/debate` | WebSocket (로컬 에이전트 전용) |
| `models` | `/api/models` | LLM 모델 목록·선호 모델 설정 |
| `usage` | `/api/usage` | 내 토큰 사용량 조회 |
| `admin/*` | `/api/admin/*` | 관리자 기능 (RBAC 필수) |
