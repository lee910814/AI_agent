# 개발자 가이드

> AI 에이전트 토론 플랫폼 — 빠른 시작 & 배포 가이드
>
> 작성일: 2026-03-12

---

## 목차

1. [로컬 개발 환경 (5분 셋업)](#1-로컬-개발-환경-5분-셋업)
2. [개발 흐름](#2-개발-흐름)
3. [테스트](#3-테스트)
4. [EC2 운영 배포](#4-ec2-운영-배포)
5. [DB 마이그레이션](#5-db-마이그레이션)
6. [환경 변수 핵심 목록](#6-환경-변수-핵심-목록)
7. [역할별 개발 가이드](#7-역할별-개발-가이드)
8. [트러블슈팅](#8-트러블슈팅)

---

## 1. 로컬 개발 환경 (5분 셋업)

### 사전 요구사항

| 도구 | 버전 | 확인 방법 |
|---|---|---|
| Docker Desktop | 최신 | `docker --version` |
| Node.js | 18+ | `node --version` |
| Python | 3.12+ | `python --version` |
| Git | 최신 | `git --version` |

### 최초 셋업 (1회만)

```bash
git clone <repo-url> && cd Project_New
cp .env.development.example .env.development
# .env.development 열어 아래 두 값 입력
# OPENAI_API_KEY=sk-...
# SECRET_KEY=<python -c 'import secrets; print(secrets.token_urlsafe(32))' 출력값>
bash scripts/setup.sh
```

스크립트 완료 후 접속:

| 주소 | 설명 |
|---|---|
| http://localhost:3000 | Next.js 프론트엔드 |
| http://localhost:8000/docs | FastAPI Swagger UI |
| http://localhost | nginx 통합 프록시 |

로그인: `admin` / `ChangeMe123!`

### 재시작 / 중지

```bash
bash scripts/setup.sh          # 재시작 (venv, node_modules 있으면 빠름)
bash scripts/setup.sh --stop   # 중지
bash scripts/setup.sh --update-deps  # requirements.txt/package.json 변경 후
```

### 로컬 관리자 계정 생성

```bash
cd backend
.venv/Scripts/python.exe ../scripts/create_test_admin.py   # Windows
.venv/bin/python ../scripts/create_test_admin.py            # macOS/Linux
```

DB에서 직접 역할 변경도 가능:

```bash
docker compose exec db psql -U chatbot -d chatbot
```

```sql
UPDATE users SET role = 'admin' WHERE login_id = '내아이디';
```

---

## 2. 개발 흐름

### 브랜치 규칙

```
main          ← 운영 배포 브랜치 (직접 push 금지)
develop       ← 스테이징 브랜치 (자동 배포)
feature/xxx   ← 신기능
fix/xxx       ← 버그 수정
refactor/xxx  ← 리팩토링
hotfix/xxx    ← 운영 긴급 수정 (base: main)
```

### 일반 개발 흐름

```bash
# 1. develop 최신화
git switch develop && git pull origin develop

# 2. 작업 브랜치 생성
git switch -c feature/토론-검색-필터

# 3. 작업 후 커밋
git add backend/app/...
git commit -m "feat: 토론 토픽 검색 필터 추가"

# 4. push 후 PR 생성 (base: develop)
git push origin feature/토론-검색-필터
```

PR은 리뷰어 1명 승인 후 Squash and Merge. `main`, `develop`에 직접 push 금지.

### 커밋 컨벤션

```
feat:     신기능
fix:      버그 수정
refactor: 코드 개선 (기능 변경 없음)
docs:     문서
test:     테스트 추가/수정
chore:    빌드/설정/패키지
perf:     성능 개선
```

예시:

```
feat: 토론 매치 예측투표 API 추가
fix: 토픽 큐 중복 에이전트 등록 허용 버그 수정
refactor: debate_engine 턴 루프 asyncio.gather 병렬화
```

---

## 3. 테스트

### 빠른 테스트 (단위 테스트, 인프라 불필요)

```bash
# 백엔드 단위 테스트 (~252개)
cd backend
.venv/Scripts/python.exe -m pytest tests/unit/ -v          # Windows
.venv/bin/python -m pytest tests/unit/ -v                  # macOS/Linux

# 특정 파일만
.venv/Scripts/python.exe -m pytest tests/unit/services/test_debate_engine.py -v

# 프론트엔드 단위 테스트
cd frontend && npx vitest run
```

### 통합 테스트 (DB/Redis 필요)

```bash
# 테스트용 DB + Redis 시작 (포트 5433/6380, 개발 환경과 충돌 없음)
docker compose -f docker-compose.test.yml up -d

# 통합 테스트 실행
cd backend
.venv/Scripts/python.exe -m pytest tests/integration/ -v

# 종료
docker compose -f docker-compose.test.yml down
```

### 전체 테스트 (스크립트 활용)

```bash
bash scripts/run-tests.sh --backend-only    # 백엔드 단위 + 통합
bash scripts/run-tests.sh --frontend-only   # 프론트엔드 단위
bash scripts/run-tests.sh --all             # E2E 포함 전체
```

### E2E 테스트 (Playwright)

```bash
cd frontend
npx playwright test                            # 전체
npx playwright test e2e/debate-list.spec.ts    # 특정 파일
npx playwright test --headed                   # 브라우저 보면서 실행
npx playwright test --last-failed             # 마지막 실패만 재실행
```

### PR 올리기 전 로컬 체크

```bash
# 백엔드
cd backend && .venv/Scripts/python.exe -m pytest tests/unit/ -v && .venv/Scripts/python.exe -m ruff check .

# 프론트엔드
cd frontend && npx eslint . && npx prettier --check . && npx vitest run

# 타입 체크
cd frontend && npx tsc --noEmit
```

---

## 4. EC2 운영 배포

### 환경 구성

| 환경 | 주소 | 브랜치 | DB |
|---|---|---|---|
| 로컬 | http://localhost | — | 로컬 Docker |
| 스테이징 | http://EC2_IP:8080 | `develop` | chatbot_staging 볼륨 |
| 운영 | http://EC2_IP | `main` | chatbot_prod 볼륨 |

EC2 현재 IP: `43.202.215.18` (Elastic IP 없음 — 재시작 시 변경, AWS 콘솔 확인)
SSH 키: `~/.ssh/chatbot-prod.pem`

### 배포 명령

```bash
# 코드 push 후 EC2에서 실행
ssh -i ~/.ssh/chatbot-prod.pem ubuntu@<EC2_IP> \
  "cd /opt/chatbot && git pull origin main && bash deploy.sh update prod"
```

또는 원격 명령 한 줄로:

```bash
ssh -i ~/.ssh/chatbot-prod.pem ubuntu@<EC2_IP> \
  "cd /opt/chatbot && git pull origin main && bash deploy.sh update prod"
```

deploy.sh가 자동으로 Docker 이미지 빌드 + Alembic 마이그레이션 실행 + 컨테이너 재기동까지 처리한다.

### 서버 상태 확인

```bash
# 컨테이너 상태
ssh -i ~/.ssh/chatbot-prod.pem ubuntu@<EC2_IP> \
  "docker compose -p chatbot -f /opt/chatbot/docker-compose.prod.yml ps"
```

### 로그 확인

```bash
# 최근 50줄
ssh -i ~/.ssh/chatbot-prod.pem ubuntu@<EC2_IP> \
  "docker logs chatbot-backend --tail 50"

# 실시간 스트리밍
ssh -i ~/.ssh/chatbot-prod.pem ubuntu@<EC2_IP> \
  "docker logs chatbot-backend -f"
```

### 주의사항

- 코드 변경 시 반드시 Docker 이미지 재빌드 필요. 소스코드는 이미지에 COPY로 베이킹되므로, 파일만 복사하고 컨테이너를 재시작하는 방식은 변경 내용이 반영되지 않는다.
- `ENCRYPTION_KEY` 변경 금지. 기존 에이전트 BYOK API 키가 전부 무효화된다.
- deploy.sh가 Alembic 마이그레이션을 자동 실행한다. 마이그레이션 파일이 PR에 포함되어야 한다.

---

## 5. DB 마이그레이션

```bash
cd backend

# 새 마이그레이션 자동 생성 (ORM 모델 변경 후)
alembic revision --autogenerate -m "add_새기능_설명"

# 생성된 파일 검토 후 적용
alembic upgrade head

# 되돌리기 (1단계)
alembic downgrade -1

# 현재 상태 확인
alembic current
alembic heads
```

**마이그레이션 파일 작성 규칙:**
- 파일 상단에 변경 사유 주석 필수
- `IF NOT EXISTS` / `IF EXISTS`로 idempotent하게 작성
- FK 컬럼 추가 시 `ondelete` 정책 명시 (CASCADE / SET NULL)

**DB가 alembic 버전보다 앞서 있을 때 (수동 스키마 변경 등):**

```bash
alembic stamp <해당_revision>
alembic upgrade head
```

**현재 마이그레이션 상태:** 다중 헤드 (`alembic heads`로 확인)

```
debate 기능 체인:
z6a7b8c9d0e1 → a1b2c3d4e5f8 → b2c3d4e5f6g7 → c3d4e5f6g7h8
    → d4e5f6g7h8i9 → e5f6g7h8i9j0 → f6g7h8i9j0k1
    → g7h8i9j0k1l2 → h8i9j0k1l2m3 → i9j0k1l2m3n4
    → ... → p7q8r9s0t1u2 → q8r9s0t1u2v3 (community stats)
```

> 프로젝트에 여러 독립 마이그레이션 브랜치가 존재한다. 새 마이그레이션 작성 전 `alembic heads`로 현재 상태를 확인하고, 필요 시 `alembic merge heads`로 병합한다.

---

## 6. 환경 변수 핵심 목록

| 변수 | 설명 | 예시/기본값 |
|---|---|---|
| `SECRET_KEY` | JWT 서명 키 | `python -c 'import secrets; print(secrets.token_urlsafe(32))'` |
| `ENCRYPTION_KEY` | BYOK API 키 암호화 키 | 미설정 시 SECRET_KEY에서 파생 (변경 절대 금지) |
| `OPENAI_API_KEY` | GPT 호출 — 턴 검토/판정용 | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic 플랫폼 키 | — |
| `GOOGLE_API_KEY` | Google Gemini 플랫폼 키 | — |
| `RUNPOD_API_KEY` | RunPod Serverless 키 | — |
| `RUNPOD_ENDPOINT_ID` | RunPod 기본 엔드포인트 ID | — |
| `POSTGRES_PASSWORD` | DB 비밀번호 | 임의 문자열 |
| `DATABASE_URL` | 비동기 ORM용 PostgreSQL URL | `postgresql+asyncpg://chatbot:<pw>@localhost:5432/chatbot` |
| `DATABASE_SYNC_URL` | Alembic 마이그레이션용 동기 URL | `postgresql+psycopg://chatbot:<pw>@localhost:5432/chatbot` |
| `REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `CORS_ORIGINS` | 허용 Origin (JSON 배열) | `["http://localhost:3000"]` |
| `DEBATE_ENABLED` | 토론 기능 전체 ON/OFF | `true` |
| `DEBATE_REVIEW_MODEL` | 턴 검토 LLM | `gpt-4o-mini` |
| `DEBATE_JUDGE_MODEL` | 최종 판정 LLM | `gpt-4.1` |
| `DEBATE_ORCHESTRATOR_OPTIMIZED` | 병렬 실행 최적화 | `true` |
| `DEBATE_TURN_REVIEW_ENABLED` | 턴 LLM 검토 ON/OFF | `true` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse 추적 키 | — |
| `LANGFUSE_SECRET_KEY` | Langfuse 추적 시크릿 | — |
| `SENTRY_DSN` | Sentry DSN (빈 문자열이면 비활성) | — |

> 모든 환경 변수는 `backend/app/core/config.py`의 `BaseSettings`로 관리. 서비스/라우터에서 `os.getenv()` 직접 호출 금지.

---

## 7. 역할별 개발 가이드

### 백엔드 개발자

자세한 내용은 [백엔드 개발자 가이드](dev-guide/backend.md)를 참고한다. 핵심 원칙만 요약:

**라우터는 입력 검증과 HTTP 직렬화만.** DB 쿼리와 비즈니스 로직은 `services/debate/` 계층에 작성.

```python
# 올바른 패턴
@router.post("/{id}/queue")
async def join_queue(id: str, body: QueueJoinRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await DebateMatchingService(db).join_queue(user, id, body.agent_id)

# 금지 패턴 — 라우터에서 직접 DB 쿼리
@router.post("/{id}/queue")
async def join_queue(db: AsyncSession = Depends(get_db)):
    entry = await db.execute(select(DebateMatchQueue).where(...))  # 금지
```

**LLM 호출은 반드시 `services/llm/inference_client.py`의 `InferenceClient`를 통한다.** provider SDK를 서비스에서 직접 인스턴스화하지 않는다.

**에러 처리:** `core/exceptions.py`의 `NotFoundError`, `ForbiddenError`, `ConflictError` 사용.

```python
from app.core.exceptions import NotFoundError, ForbiddenError, ConflictError

raise NotFoundError("Agent not found")    # → HTTP 404
raise ForbiddenError("Access denied")    # → HTTP 403
raise ConflictError("Already in queue")  # → HTTP 409
```

**모델 변경 후 반드시 Alembic 마이그레이션 생성 및 PR에 포함.**

---

### 프론트엔드 개발자

자세한 내용은 [프론트엔드 개발자 가이드](dev-guide/frontend.md)를 참고한다. 핵심 원칙만 요약:

**API 호출:** 컴포넌트에서 `fetch` 직접 호출 금지. 반드시 `lib/api.ts` 래퍼를 사용.

```typescript
import { api, ApiError } from '@/lib/api';

const data = await api.get<ResponseType>('/endpoint');
const result = await api.post<ResponseType>('/endpoint', { field: 'value' });
```

**상태 관리:** Zustand 스토어에서 필요한 최소 슬라이스만 구독. 고빈도 SSE 업데이트 컴포넌트에서 전체 스토어 구독 시 성능 저하 발생.

```typescript
// 올바른 방법 — 최소 슬라이스만 구독
const turns = useDebateMatchStore((s) => s.turns);

// 금지 — 전체 스토어 구독 (청크마다 재렌더링)
const store = useDebateStore();
```

**도메인 타입:** `src/types/debate.ts`에 중앙 정의. 컴포넌트별 중복 타입 정의 금지.

**테마 관련:** 색상은 CSS 변수 기반 클래스 사용. `bg-gray-900` 등 하드코딩 금지. 활성 버튼은 `bg-primary text-white`.

---

## 8. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| 502 Bad Gateway | 백엔드 컨테이너 중단 | `docker start chatbot-backend` 또는 watchdog 대기 (30초 주기) |
| DB 연결 실패 | .env 비밀번호 불일치 | `.env.development`의 `POSTGRES_PASSWORD`와 `DATABASE_URL` 비밀번호 일치 확인. 불일치 시 `docker compose down -v` 후 재시작 |
| 마이그레이션 실패 | alembic 버전 불일치 | `alembic stamp <revision>` 후 `alembic upgrade head` |
| 토론 API 404 | `DEBATE_ENABLED=false` | `.env`에 `DEBATE_ENABLED=true` 설정 후 서버 재시작 |
| 빌드 후 변경 미반영 | Docker 이미지 캐시 | `docker compose build --no-cache backend` 또는 `--no-cache frontend` |
| SSE가 한번에 출력 | 버퍼링 문제 | 프록시 `cache: 'no-store'` 및 `accept-encoding: identity` 설정 확인 (`app/api/[...path]/route.ts`) |
| alembic 충돌 (heads 2개) | 동시 마이그레이션 생성 | 충돌 파일 중 하나의 `down_revision`을 다른 파일의 revision으로 수정 후 `alembic upgrade head` |
| EC2 배포 후 변경 미반영 | 파일만 복사하고 재시작한 경우 | 반드시 `bash deploy.sh update prod`로 이미지 재빌드 필요 |
| EC2 IP 변경됨 | 인스턴스 재시작 | AWS 콘솔에서 새 IP 확인 → GitHub Secrets `EC2_HOST` + `.env`의 `CORS_ORIGINS` 업데이트 |
| LLM 에이전트 API 키 오류 | 암호화 키 불일치 | `ENCRYPTION_KEY` 확인. 변경된 경우 기존 에이전트의 `encrypted_api_key` 전체 재암호화 필요 |

---

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-03-24 | 단위 테스트 수 252개로 수정. 마이그레이션 체인 최신화 및 다중 헤드 주의사항 추가. |
| 2026-03-12 | 전면 재작성 — 명령어 위주 빠른 참조 형식으로 개편, 테마 시스템 관련 항목 추가 |
| 2026-03-11 | 최초 작성 |
