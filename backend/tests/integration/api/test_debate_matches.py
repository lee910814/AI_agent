"""매치 API 통합 테스트."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_match import DebateMatch
from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_get_match(
    client: AsyncClient, test_developer, test_debate_agent, test_debate_topic, db_session
):
    """매치 상세를 조회할 수 있다."""
    match = DebateMatch(
        id=uuid.uuid4(),
        topic_id=test_debate_topic.id,
        agent_a_id=test_debate_agent.id,
        agent_b_id=test_debate_agent.id,
        status="completed",
        score_a=75,
        score_b=60,
    )
    db_session.add(match)
    await db_session.commit()

    response = await client.get(
        f"/api/matches/{match.id}",
        headers=auth_header(test_developer),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["score_a"] == 75


@pytest.mark.asyncio
async def test_get_match_not_found(client: AsyncClient, test_developer):
    """존재하지 않는 매치는 404를 반환한다."""
    response = await client.get(
        f"/api/matches/{uuid.uuid4()}",
        headers=auth_header(test_developer),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_scorecard_not_available(
    client: AsyncClient, test_developer, test_debate_agent, test_debate_topic, db_session
):
    """스코어카드가 없는 매치는 404를 반환한다."""
    match = DebateMatch(
        id=uuid.uuid4(),
        topic_id=test_debate_topic.id,
        agent_a_id=test_debate_agent.id,
        agent_b_id=test_debate_agent.id,
        status="in_progress",
    )
    db_session.add(match)
    await db_session.commit()

    response = await client.get(
        f"/api/matches/{match.id}/scorecard",
        headers=auth_header(test_developer),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_scorecard_completed(
    client: AsyncClient, test_developer, test_debate_agent, test_debate_topic, db_session
):
    """완료된 매치의 스코어카드를 조회할 수 있다."""
    match = DebateMatch(
        id=uuid.uuid4(),
        topic_id=test_debate_topic.id,
        agent_a_id=test_debate_agent.id,
        agent_b_id=test_debate_agent.id,
        status="completed",
        winner_id=test_debate_agent.id,
        scorecard={
            "agent_a": {"logic": 28, "evidence": 22, "rebuttal": 20, "relevance": 18},
            "agent_b": {"logic": 20, "evidence": 18, "rebuttal": 15, "relevance": 14},
            "reasoning": "Agent A demonstrated superior logic and evidence usage.",
        },
        score_a=88,
        score_b=67,
    )
    db_session.add(match)
    await db_session.commit()

    response = await client.get(
        f"/api/matches/{match.id}/scorecard",
        headers=auth_header(test_developer),
    )
    assert response.status_code == 200
    data = response.json()
    assert "agent_a" in data
    assert "reasoning" in data


@pytest.mark.asyncio
async def test_list_matches(
    client: AsyncClient, test_developer, test_debate_agent, test_debate_topic, db_session
):
    """매치 목록을 조회할 수 있다."""
    match = DebateMatch(
        id=uuid.uuid4(),
        topic_id=test_debate_topic.id,
        agent_a_id=test_debate_agent.id,
        agent_b_id=test_debate_agent.id,
        status="completed",
    )
    db_session.add(match)
    await db_session.commit()

    response = await client.get("/api/matches", headers=auth_header(test_developer))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_sse_stream_endpoint(
    client: AsyncClient, test_developer, test_debate_agent, test_debate_topic, db_session
):
    """SSE 스트림 엔드포인트가 존재하고 올바른 content-type을 반환한다."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    match = DebateMatch(
        id=uuid.uuid4(),
        topic_id=test_debate_topic.id,
        agent_a_id=test_debate_agent.id,
        agent_b_id=test_debate_agent.id,
        status="in_progress",
    )
    db_session.add(match)
    await db_session.commit()

    # subscribe를 mock하여 한 번의 이벤트만 발행 후 종료
    async def mock_subscribe(match_id):
        yield 'data: {"event": "finished", "data": {}}\n\n'

    with patch("app.api.debate_matches.subscribe", side_effect=mock_subscribe):
        response = await client.get(
            f"/api/matches/{match.id}/stream",
            headers=auth_header(test_developer),
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
