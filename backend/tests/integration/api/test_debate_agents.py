"""에이전트 API 통합 테스트."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_create_agent_returns_201(client: AsyncClient, test_user, db_session):
    """로그인한 사용자가 에이전트를 생성하면 201을 반환한다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "My Agent",
            "description": "A test agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key-123",
            "system_prompt": "You are a skilled debater.",
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Agent"
    assert data["provider"] == "openai"
    assert data["elo_rating"] == 1500
    assert "encrypted_api_key" not in data  # API 키는 응답에 포함하지 않음


@pytest.mark.asyncio
async def test_create_agent_unauthorized(client: AsyncClient):
    """비로그인 사용자는 에이전트를 생성할 수 없다 (401)."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "key",
            "system_prompt": "prompt",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_my_agents(client: AsyncClient, test_user, test_debate_agent):
    """내 에이전트 목록을 조회할 수 있다."""
    response = await client.get("/api/agents/me", headers=auth_header(test_user))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_agent_versions(client: AsyncClient, test_developer, test_debate_agent):
    """소유자는 에이전트 버전 이력을 조회할 수 있다."""
    response = await client.get(
        f"/api/agents/{test_debate_agent.id}/versions",
        headers=auth_header(test_developer),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["version_number"] == 1


@pytest.mark.asyncio
async def test_get_agent_versions_not_owner(client: AsyncClient, test_user, test_debate_agent):
    """비소유자가 버전 이력(system_prompt 포함) 조회 시 403을 반환한다."""
    response = await client.get(
        f"/api/agents/{test_debate_agent.id}/versions",
        headers=auth_header(test_user),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_agent_creates_new_version(
    client: AsyncClient, test_developer, test_debate_agent
):
    """프롬프트 변경 시 새 버전이 자동 생성된다."""
    response = await client.put(
        f"/api/agents/{test_debate_agent.id}",
        json={
            "system_prompt": "Updated prompt for v2.",
            "version_tag": "v2",
        },
        headers=auth_header(test_developer),
    )
    assert response.status_code == 200

    versions_resp = await client.get(
        f"/api/agents/{test_debate_agent.id}/versions",
        headers=auth_header(test_developer),
    )
    versions = versions_resp.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2


@pytest.mark.asyncio
async def test_create_local_agent_no_api_key(client: AsyncClient, test_user):
    """local 에이전트는 API 키 없이 생성할 수 있다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "My Local Agent",
            "description": "A local agent",
            "provider": "local",
            "model_id": "custom",
            "system_prompt": "You are a local debater.",
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "local"
    assert data["model_id"] == "custom"
    assert data["is_connected"] is False


@pytest.mark.asyncio
async def test_create_local_agent_with_api_key_ignored(client: AsyncClient, test_user):
    """local 에이전트에 api_key를 넣어도 정상 생성된다 (무시)."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Local With Key",
            "provider": "local",
            "model_id": "custom",
            "api_key": "sk-not-needed",
            "system_prompt": "Test prompt.",
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 201
    assert response.json()["provider"] == "local"


@pytest.mark.asyncio
async def test_create_non_local_agent_requires_api_key(client: AsyncClient, test_user):
    """non-local 에이전트는 API 키 없이 생성하면 422를 반환한다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "No Key Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "system_prompt": "Test prompt.",
        },
        headers=auth_header(test_user),
    )
    # api_key가 None이면 provider != local이라 서비스에서 ValueError → 422
    assert response.status_code == 422
    assert "API key is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_local_agent_without_system_prompt(client: AsyncClient, test_user):
    """로컬 에이전트는 시스템 프롬프트 없이 생성할 수 있다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Local No Prompt",
            "provider": "local",
            "model_id": "custom",
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "local"


@pytest.mark.asyncio
async def test_create_api_agent_requires_system_prompt(client: AsyncClient, test_user):
    """API 에이전트는 시스템 프롬프트 없이 생성하면 422를 반환한다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "No Prompt Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key-123",
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 422
    assert "System prompt is required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_ranking(client: AsyncClient, test_user, test_debate_agent):
    """ELO 랭킹을 조회할 수 있다."""
    response = await client.get("/api/agents/ranking", headers=auth_header(test_user))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_delete_agent_success(client: AsyncClient, test_developer, test_debate_agent):
    """소유자가 자신의 에이전트를 삭제하면 204를 반환한다."""
    response = await client.delete(
        f"/api/agents/{test_debate_agent.id}",
        headers=auth_header(test_developer),
    )
    assert response.status_code == 204

    # 삭제 후 조회하면 404
    get_resp = await client.get(
        f"/api/agents/{test_debate_agent.id}",
        headers=auth_header(test_developer),
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent_not_owner(client: AsyncClient, test_user, test_debate_agent):
    """소유자가 아닌 사용자가 삭제하면 403을 반환한다."""
    response = await client.delete(
        f"/api/agents/{test_debate_agent.id}",
        headers=auth_header(test_user),
    )
    assert response.status_code == 403
    assert "Permission denied" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_agent_not_found(client: AsyncClient, test_developer):
    """존재하지 않는 에이전트 삭제 시 404를 반환한다."""
    import uuid
    response = await client.delete(
        f"/api/agents/{uuid.uuid4()}",
        headers=auth_header(test_developer),
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_agent_unauthorized(client: AsyncClient, test_debate_agent):
    """비로그인 사용자가 삭제하면 403을 반환한다."""
    response = await client.delete(f"/api/agents/{test_debate_agent.id}")
    assert response.status_code == 403
