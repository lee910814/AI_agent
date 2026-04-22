"""로컬 에이전트 WebSocket 엔드포인트 통합 테스트."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.core.auth import create_access_token
from app.main import app
from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_ws_connect_with_valid_token(
    client: AsyncClient, test_developer, test_local_debate_agent, db_session
):
    """유효한 JWT + local 에이전트로 WebSocket 접속이 성공한다."""
    token = create_access_token({"sub": str(test_developer.id), "role": test_developer.role})

    # starlette TestClient로 WebSocket 테스트
    test_client = TestClient(app)
    with test_client.websocket_connect(
        f"/ws/agent/{test_local_debate_agent.id}?token={token}"
    ) as ws:
        # 연결 성공 확인 — heartbeat ping 수신 대기 (또는 바로 닫기)
        ws.close()


@pytest.mark.asyncio
async def test_ws_connect_unauthorized(client: AsyncClient, test_local_debate_agent):
    """잘못된 토큰으로 WebSocket 접속 시 연결이 거부된다."""
    test_client = TestClient(app)
    with pytest.raises(Exception):
        with test_client.websocket_connect(
            f"/ws/agent/{test_local_debate_agent.id}?token=invalid-token"
        ) as ws:
            ws.receive_json()


@pytest.mark.asyncio
async def test_ws_connect_wrong_provider(
    client: AsyncClient, test_developer, test_debate_agent, db_session
):
    """provider가 local이 아닌 에이전트로 WebSocket 접속 시 거부된다."""
    token = create_access_token({"sub": str(test_developer.id), "role": test_developer.role})

    test_client = TestClient(app)
    with pytest.raises(Exception):
        with test_client.websocket_connect(
            f"/ws/agent/{test_debate_agent.id}?token={token}"
        ) as ws:
            ws.receive_json()


@pytest.mark.asyncio
async def test_ws_connect_not_owner(
    client: AsyncClient, test_user, test_local_debate_agent, db_session
):
    """타인의 에이전트로 WebSocket 접속 시 거부된다."""
    token = create_access_token({"sub": str(test_user.id), "role": test_user.role})

    test_client = TestClient(app)
    with pytest.raises(Exception):
        with test_client.websocket_connect(
            f"/ws/agent/{test_local_debate_agent.id}?token={token}"
        ) as ws:
            ws.receive_json()


@pytest.mark.asyncio
async def test_ws_connect_nonexistent_agent(client: AsyncClient, test_developer, db_session):
    """존재하지 않는 에이전트로 WebSocket 접속 시 거부된다."""
    token = create_access_token({"sub": str(test_developer.id), "role": test_developer.role})

    test_client = TestClient(app)
    with pytest.raises(Exception):
        with test_client.websocket_connect(
            f"/ws/agent/{uuid.uuid4()}?token={token}"
        ) as ws:
            ws.receive_json()
