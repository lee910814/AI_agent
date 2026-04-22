"""토론 주제 API 통합 테스트."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_api_key
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_create_topic_admin_only(client: AsyncClient, test_admin):
    """관리자만 토론 주제를 생성할 수 있다."""
    response = await client.post(
        "/api/topics",
        json={"title": "AI와 윤리", "description": "AI 윤리 논쟁", "max_turns": 4},
        headers=auth_header(test_admin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "AI와 윤리"
    assert data["status"] == "open"


@pytest.mark.asyncio
async def test_create_topic_forbidden_for_user(client: AsyncClient, test_developer):
    """일반 사용자는 토론 주제를 생성할 수 없다 (관리자 전용)."""
    response = await client.post(
        "/api/topics",
        json={"title": "Test Topic"},
        headers=auth_header(test_developer),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_topics(client: AsyncClient, test_developer, test_debate_topic):
    """토론 주제 목록을 조회할 수 있다."""
    response = await client.get("/api/topics", headers=auth_header(test_developer))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_get_topic(client: AsyncClient, test_developer, test_debate_topic):
    """특정 토론 주제를 조회할 수 있다."""
    response = await client.get(
        f"/api/topics/{test_debate_topic.id}",
        headers=auth_header(test_developer),
    )
    assert response.status_code == 200
    assert response.json()["title"] == test_debate_topic.title


@pytest.mark.asyncio
async def test_join_queue(client: AsyncClient, test_developer, test_debate_agent, test_debate_topic):
    """에이전트가 큐에 참가할 수 있다."""
    response = await client.post(
        f"/api/topics/{test_debate_topic.id}/join",
        json={"agent_id": str(test_debate_agent.id)},
        headers=auth_header(test_developer),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_join_queue_auto_match(
    client: AsyncClient, test_developer, test_debate_agent, test_debate_topic, db_session
):
    """2명이 큐에 참가하면 자동으로 매치가 생성된다."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    # 두 번째 사용자 + 에이전트 생성
    dev2 = User(
        id=uuid.uuid4(),
        login_id="testdev2",
        nickname="testdev2",
        password_hash=get_password_hash("devpass2"),
        role="user",
        age_group="unverified",
    )
    db_session.add(dev2)
    await db_session.flush()

    agent2 = DebateAgent(
        id=uuid.uuid4(),
        owner_id=dev2.id,
        name="Agent 2",
        provider="openai",
        model_id="gpt-4o",
        encrypted_api_key=encrypt_api_key("sk-test-2"),
    )
    db_session.add(agent2)
    await db_session.flush()

    version2 = DebateAgentVersion(
        agent_id=agent2.id,
        version_number=1,
        version_tag="v1",
        system_prompt="Agent 2 prompt.",
    )
    db_session.add(version2)
    await db_session.commit()

    # 첫 번째 참가
    await client.post(
        f"/api/topics/{test_debate_topic.id}/join",
        json={"agent_id": str(test_debate_agent.id)},
        headers=auth_header(test_developer),
    )

    # 두 번째 참가 → 자동 매치
    response = await client.post(
        f"/api/topics/{test_debate_topic.id}/join",
        json={"agent_id": str(agent2.id)},
        headers=auth_header(dev2),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "matched"
    assert "match_id" in data
