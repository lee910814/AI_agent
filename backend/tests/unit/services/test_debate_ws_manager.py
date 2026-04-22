"""WebSocket 연결 관리자 단위 테스트."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.debate_ws import WSTurnRequest, WSTurnResponse
from app.services.debate.ws_manager import WSConnectionManager


@pytest.fixture(autouse=True)
def reset_singleton():
    """각 테스트마다 싱글턴 인스턴스 초기화."""
    WSConnectionManager._instance = None
    yield
    WSConnectionManager._instance = None


def _make_mock_ws(connected: bool = True) -> MagicMock:
    """WebSocket mock 생성."""
    from starlette.websockets import WebSocketState

    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
    ws.send_json = AsyncMock()
    return ws


def _make_turn_request(match_id: uuid.UUID | None = None) -> WSTurnRequest:
    return WSTurnRequest(
        match_id=match_id or uuid.uuid4(),
        turn_number=1,
        speaker="agent_a",
        topic_title="Test Topic",
        topic_description=None,
        max_turns=6,
        turn_token_limit=500,
        my_previous_claims=[],
        opponent_previous_claims=[],
        time_limit_seconds=60,
    )


class TestWSConnectionManager:
    @pytest.mark.asyncio
    @patch("app.services.debate.ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_connect_registers_agent(self, mock_presence):
        """접속 시 _connections에 등록된다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)

        assert manager.is_connected(agent_id) is True
        mock_presence.assert_called_once_with(agent_id, True)

    @pytest.mark.asyncio
    @patch("app.services.debate.ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_disconnect_clears_agent(self, mock_presence):
        """해제 시 정리되고 Queue에 _disconnect 신호가 전달된다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)
        assert manager.is_connected(agent_id) is True

        # pending queue 생성 (agent_id 포함 키 — 레거시 경로)
        queue: asyncio.Queue = asyncio.Queue()
        key_with_agent = f"{agent_id}:1:agent_a"
        manager._pending_turns[key_with_agent] = queue

        await manager.disconnect(agent_id)

        assert manager.is_connected(agent_id) is False
        assert key_with_agent not in manager._pending_turns
        # Queue에 disconnect 신호가 전달됐는지 확인
        sentinel = queue.get_nowait()
        assert sentinel == {"type": "_disconnect"}

    @pytest.mark.asyncio
    @patch("app.services.debate.ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_request_turn_resolves_on_response(self, mock_presence):
        """턴 요청 후 응답 수신 시 Future가 resolve된다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        match_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)

        request = _make_turn_request(match_id)

        async def simulate_response():
            """응답을 짧은 지연 후 전송하여 Future resolve."""
            await asyncio.sleep(0.05)
            response_data = {
                "type": "turn_response",
                "match_id": str(match_id),
                "action": "argue",
                "claim": "Test claim",
                "evidence": None,
            }
            await manager.handle_message(agent_id, response_data)

        task = asyncio.create_task(simulate_response())
        result = await asyncio.wait_for(
            manager.request_turn(match_id, agent_id, request),
            timeout=2.0,
        )
        await task

        assert isinstance(result, WSTurnResponse)
        assert result.action == "argue"
        assert result.claim == "Test claim"

    @pytest.mark.asyncio
    @patch("app.services.debate.ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_request_turn_timeout(self, mock_presence):
        """타임아웃 시 TimeoutError가 발생한다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)

        request = _make_turn_request()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                manager.request_turn(uuid.uuid4(), agent_id, request),
                timeout=0.1,
            )

    @pytest.mark.asyncio
    @patch("app.services.debate.ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_handle_invalid_message(self, mock_presence):
        """잘못된 메시지는 에러 없이 무시된다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()

        # 잘못된 type
        await manager.handle_message(agent_id, {"type": "unknown"})

        # turn_response이지만 필수 필드 누락
        await manager.handle_message(agent_id, {"type": "turn_response", "action": "argue"})

    @pytest.mark.asyncio
    async def test_is_connected_returns_false_for_unknown_agent(self):
        """등록되지 않은 에이전트는 False."""
        manager = WSConnectionManager.get_instance()
        assert manager.is_connected(uuid.uuid4()) is False

    @pytest.mark.asyncio
    async def test_request_turn_raises_on_disconnected(self):
        """미접속 에이전트에 턴 요청 시 ConnectionError."""
        manager = WSConnectionManager.get_instance()

        with pytest.raises(ConnectionError):
            await manager.request_turn(uuid.uuid4(), uuid.uuid4(), _make_turn_request())

    @pytest.mark.asyncio
    @patch("app.services.debate.ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_request_turn_handles_tool_request(self, mock_presence):
        """턴 중 tool_request를 처리하고 tool_result를 전송한 후 turn_response를 반환한다."""
        from app.services.debate.tool_executor import DebateToolExecutor, ToolContext

        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        match_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)

        request = _make_turn_request(match_id)
        tool_ctx = ToolContext(turn_number=1, max_turns=6, speaker="agent_a")

        async def simulate_tool_then_response():
            await asyncio.sleep(0.05)
            # 에이전트가 tool_request 전송
            await manager.handle_message(agent_id, {
                "type": "tool_request",
                "match_id": str(match_id),
                "turn_number": 1,
                "tool_name": "turn_info",
                "tool_input": "",
            })
            await asyncio.sleep(0.05)
            # 에이전트가 turn_response 전송
            await manager.handle_message(agent_id, {
                "type": "turn_response",
                "match_id": str(match_id),
                "action": "argue",
                "claim": "Claim after tool use",
                "evidence": None,
            })

        task = asyncio.create_task(simulate_tool_then_response())
        result = await asyncio.wait_for(
            manager.request_turn(match_id, agent_id, request,
                                 tool_executor=DebateToolExecutor(), tool_context=tool_ctx),
            timeout=3.0,
        )
        await task

        # turn_response 정상 반환
        assert isinstance(result, WSTurnResponse)
        assert result.claim == "Claim after tool use"
        # tool_result가 에이전트에게 전송됐는지 확인 (2회 send_json: turn_request + tool_result)
        assert ws.send_json.call_count >= 2

    @pytest.mark.asyncio
    @patch("app.services.debate.ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_request_turn_sends_error_tool_result_without_executor(self, mock_presence):
        """tool_executor 없이 tool_request가 오면 error tool_result를 전송하고 계속 대기한다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        match_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)

        request = _make_turn_request(match_id)

        async def simulate_tool_then_response():
            await asyncio.sleep(0.05)
            await manager.handle_message(agent_id, {
                "type": "tool_request",
                "match_id": str(match_id),
                "turn_number": 1,
                "tool_name": "calculator",
                "tool_input": "1+1",
            })
            await asyncio.sleep(0.05)
            await manager.handle_message(agent_id, {
                "type": "turn_response",
                "match_id": str(match_id),
                "action": "argue",
                "claim": "No tool needed",
                "evidence": None,
            })

        task = asyncio.create_task(simulate_tool_then_response())
        result = await asyncio.wait_for(
            manager.request_turn(match_id, agent_id, request),  # tool_executor 없음
            timeout=3.0,
        )
        await task

        assert isinstance(result, WSTurnResponse)
        # tool_result에 error가 설정되어 전송됐는지 확인
        tool_result_calls = [
            call for call in ws.send_json.call_args_list
            if call.args[0].get("type") == "tool_result"
        ]
        assert len(tool_result_calls) == 1
        assert tool_result_calls[0].args[0]["error"] is not None

    @pytest.mark.asyncio
    @patch("app.services.debate.ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_request_turn_raises_on_agent_disconnect(self, mock_presence):
        """턴 대기 중 에이전트가 접속 해제되면 ConnectionError가 발생한다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        match_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)
        request = _make_turn_request(match_id)

        async def disconnect_mid_turn():
            await asyncio.sleep(0.05)
            await manager.disconnect(agent_id)

        task = asyncio.create_task(disconnect_mid_turn())
        with pytest.raises(ConnectionError):
            await asyncio.wait_for(
                manager.request_turn(match_id, agent_id, request),
                timeout=2.0,
            )
        await task
