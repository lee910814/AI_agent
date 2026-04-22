"""
테스트 픽스처 및 표준 패턴.

## 단위 테스트 표준 패턴 (services/)
- DB 세션: `db_session` 픽스처 사용 (SQLite in-memory, 실제 ORM 쿼리 실행)
- LLM 호출: `AsyncMock`으로 `InferenceClient` 또는 `BaseProvider.generate` mock
- 외부 HTTP: `AsyncMock`으로 httpx 클라이언트 mock

## 통합 테스트 패턴 (integration/)
- DB: docker-compose.test.yml PostgreSQL (포트 5433)
- Redis: docker-compose.test.yml (포트 6380)

## 벤치마크 패턴 (benchmark/)
- LLM만 AsyncMock, DB는 실제 사용 또는 db_session
"""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

# DOTENV_PATH 환경변수가 지정된 경우 해당 .env 파일 로드 (테스트 Compose 지원)
_dotenv_path = os.environ.get("DOTENV_PATH")
if _dotenv_path:
    _env_file = Path(_dotenv_path)
    if _env_file.exists():
        with open(_env_file) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _key, _, _val = _line.partition("=")
                    os.environ.setdefault(_key.strip(), _val.strip())

# debate 라우트를 테스트에서 활성화하기 위해 app import 전에 환경변수 설정
os.environ.setdefault("DEBATE_ENABLED", "true")

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import create_access_token
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# DATABASE_URL 환경변수 우선 → 없으면 settings fallback
# rsplit으로 마지막 /dbname만 교체 (username의 chatbot은 유지)
_db_url = os.environ.get("DATABASE_URL", settings.database_url)
_base, _dbname = _db_url.rsplit("/", 1)
TEST_DATABASE_URL = f"{_base}/chatbot_test"


def auth_header(user) -> dict:
    """테스트용 JWT Authorization 헤더 생성."""
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def db_session():
    """단위 테스트용 SQLite in-memory 세션.

    실제 PostgreSQL 없이 ORM 쿼리를 실행할 수 있다.
    각 테스트 종료 시 테이블이 드롭되므로 격리됨.
    """
    # 이유: AsyncMock 체인 없이 실제 ORM 쿼리를 실행해 테스트 신뢰도 향상
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """일반 사용자 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        login_id="testuser",
        nickname="testuser",
        password_hash=get_password_hash("testpass"),
        role="user",
        age_group="unverified",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession):
    """관리자 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    admin = User(
        id=uuid.uuid4(),
        login_id="testadmin",
        nickname="testadmin",
        password_hash=get_password_hash("adminpass"),
        role="admin",
        age_group="adult_verified",
        adult_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def test_superadmin(db_session: AsyncSession):
    """슈퍼관리자 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    superadmin = User(
        id=uuid.uuid4(),
        login_id="testsuperadmin",
        nickname="testsuperadmin",
        password_hash=get_password_hash("superpass"),
        role="superadmin",
        age_group="adult_verified",
        adult_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(superadmin)
    await db_session.commit()
    await db_session.refresh(superadmin)
    return superadmin


@pytest_asyncio.fixture
async def test_developer(db_session: AsyncSession):
    """토론 에이전트 소유자 fixture (일반 사용자)."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        login_id="testdev",
        nickname="testdev",
        password_hash=get_password_hash("devpass"),
        role="user",
        age_group="unverified",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_debate_agent(db_session: AsyncSession, test_developer):
    """토론 에이전트 fixture."""
    from app.core.encryption import encrypt_api_key
    from app.models.debate_agent import DebateAgent
    from app.models.debate_agent import DebateAgentVersion

    agent = DebateAgent(
        id=uuid.uuid4(),
        owner_id=test_developer.id,
        name="Test Agent",
        provider="openai",
        model_id="gpt-4o",
        encrypted_api_key=encrypt_api_key("sk-test-key"),
    )
    db_session.add(agent)
    await db_session.flush()

    version = DebateAgentVersion(
        agent_id=agent.id,
        version_number=1,
        version_tag="v1",
        system_prompt="You are a test debate agent.",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_local_debate_agent(db_session: AsyncSession, test_developer):
    """로컬 에이전트 fixture (provider=local, API 키 없음)."""
    from app.models.debate_agent import DebateAgent
    from app.models.debate_agent import DebateAgentVersion

    agent = DebateAgent(
        id=uuid.uuid4(),
        owner_id=test_developer.id,
        name="Local Test Agent",
        provider="local",
        model_id="custom",
        encrypted_api_key=None,
    )
    db_session.add(agent)
    await db_session.flush()

    version = DebateAgentVersion(
        agent_id=agent.id,
        version_number=1,
        version_tag="v1",
        system_prompt="You are a local test debate agent.",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_debate_topic(db_session: AsyncSession, test_admin):
    """토론 주제 fixture."""
    from app.models.debate_topic import DebateTopic

    topic = DebateTopic(
        id=uuid.uuid4(),
        title="AI와 교육의 미래",
        description="AI가 교육을 개선할 수 있는가?",
        mode="debate",
        status="open",
        max_turns=6,
        turn_token_limit=500,
        created_by=test_admin.id,
    )
    db_session.add(topic)
    await db_session.commit()
    await db_session.refresh(topic)
    return topic


@pytest_asyncio.fixture
async def test_adult_user(db_session: AsyncSession):
    """성인인증 완료 사용자 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        login_id="adultuser",
        nickname="adultuser",
        password_hash=get_password_hash("adultpass"),
        role="user",
        age_group="adult_verified",
        adult_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
