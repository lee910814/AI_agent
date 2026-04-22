"""로컬 에이전트 WebSocket 연결 관리 (싱글턴).

턴 요청/응답 흐름:
  1. request_turn() — 에이전트에게 WSTurnRequest 전송, Queue 대기
  2. 에이전트가 WSToolRequest 전송 → execute_tool → WSToolResult 응답 (0~N회)
  3. 에이전트가 WSTurnResponse 전송 → request_turn() 반환
"""

import asyncio
import contextlib
import logging
from uuid import UUID

from starlette.websockets import WebSocket, WebSocketState

from app.schemas.debate_ws import WSMatchReady, WSTurnRequest, WSTurnResponse
from app.services.debate.tool_executor import DebateToolExecutor, ToolContext

logger = logging.getLogger(__name__)

_PRESENCE_PREFIX = "debate:agent:"
_PRESENCE_TTL = 60  # heartbeat 갱신 주기보다 충분히 길게
_PUBSUB_CHANNEL = "debate:agent:messages"


class WSConnectionManager:
    """로컬 에이전트 WebSocket 연결을 관리하는 싱글턴 클래스.

    싱글턴으로 동작하며 get_instance()로 접근한다.
    멀티 워커 환경에서는 Redis pub/sub을 통해 다른 인스턴스의 에이전트에게 메시지를 전달한다.
    """

    _instance: "WSConnectionManager | None" = None

    def __init__(self) -> None:
        self._connections: dict[UUID, WebSocket] = {}
        # key: "{match_id}:{turn_number}:{speaker}" → Queue[dict]
        self._pending_turns: dict[str, asyncio.Queue] = {}
        # agent_id → 현재 활성 턴 key (툴 메시지 라우팅용)
        self._agent_active_turn: dict[UUID, str] = {}
        self._pubsub_task: asyncio.Task | None = None

    @classmethod
    def get_instance(cls) -> "WSConnectionManager":
        """싱글턴 인스턴스를 반환한다. 없으면 새로 생성."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self, agent_id: UUID, ws: WebSocket) -> None:
        """WebSocket 등록 + Redis 프레즌스 설정.

        기존 stale 연결이 남아 있으면 정리 후 새 연결을 등록한다.
        pending Queue는 보존하여 새 연결에서 계속 처리할 수 있도록 한다.
        """
        existing_ws = self._connections.get(agent_id)
        if existing_ws is not None and existing_ws is not ws:
            await self._cleanup_stale_connection(agent_id, existing_ws)

        self._connections[agent_id] = ws
        await self._set_presence(agent_id, True)
        logger.info("Local agent %s connected via WebSocket", agent_id)

    async def _cleanup_stale_connection(self, agent_id: UUID, stale_ws: WebSocket) -> None:
        """stale WebSocket 연결을 안전하게 닫는다. pending Queue는 보존."""
        logger.info("Cleaning up stale connection for agent %s (reconnect)", agent_id)
        try:
            if stale_ws.client_state == WebSocketState.CONNECTED:
                await stale_ws.close(code=1012, reason="Replaced by new connection")
        except Exception:
            logger.debug("Failed to close stale WebSocket for agent %s (expected)", agent_id)

    async def disconnect(self, agent_id: UUID) -> None:
        """연결 해제 + Redis 프레즌스 삭제 + 대기 중 Queue에 disconnect 신호 전달."""
        self._connections.pop(agent_id, None)
        await self._set_presence(agent_id, False)

        # 활성 턴 큐에 연결 해제 신호 전달
        key = self._agent_active_turn.pop(agent_id, None)
        if key:
            queue = self._pending_turns.pop(key, None)
            if queue:
                queue.put_nowait({"type": "_disconnect"})

        # 하위 호환: key에 agent_id가 포함된 경우 (레거시 경로)
        to_clean = [k for k in list(self._pending_turns) if str(agent_id) in k]
        for k in to_clean:
            q = self._pending_turns.pop(k, None)
            if q:
                q.put_nowait({"type": "_disconnect"})

        logger.info("Local agent %s disconnected", agent_id)

    def is_connected(self, agent_id: UUID) -> bool:
        """에이전트가 현재 인스턴스에 WebSocket으로 연결되어 있는지 확인.

        Args:
            agent_id: 에이전트 UUID.

        Returns:
            로컬 연결이 CONNECTED 상태면 True, 아니면 False.
        """
        ws = self._connections.get(agent_id)
        if ws is None:
            return False
        return ws.client_state == WebSocketState.CONNECTED

    async def request_turn(
        self,
        match_id: UUID,
        agent_id: UUID,
        request: WSTurnRequest,
        tool_executor: DebateToolExecutor | None = None,
        tool_context: ToolContext | None = None,
    ) -> WSTurnResponse:
        """턴 요청 전송 + 툴 요청 처리 루프.

        에이전트가 turn_response를 보낼 때까지 tool_request를 처리한다.
        타임아웃은 caller의 asyncio.wait_for()가 담당한다.
        """
        key = f"{match_id}:{request.turn_number}:{request.speaker}"
        queue: asyncio.Queue = asyncio.Queue()
        self._pending_turns[key] = queue
        self._agent_active_turn[agent_id] = key

        try:
            ws = self._connections.get(agent_id)
            if ws is not None:
                await ws.send_json(request.model_dump(mode="json"))
            else:
                is_present = await self.check_presence(agent_id)
                if not is_present:
                    raise ConnectionError(f"Agent {agent_id} is not connected on any instance")
                await self._publish_to_agent(agent_id, request.model_dump(mode="json"))

            # 메시지 루프: turn_response가 올 때까지 tool_request 처리
            while True:
                data = await queue.get()
                msg_type = data.get("type")

                if msg_type == "turn_response":
                    try:
                        return WSTurnResponse.model_validate(data)
                    except Exception:
                        logger.warning("Invalid turn_response from agent %s: %s", agent_id, data)
                        # 재시도 — 에이전트가 다시 보내길 기다림
                        continue

                elif msg_type == "tool_request":
                    await self._handle_tool_request(agent_id, data, tool_executor, tool_context)

                elif msg_type == "_disconnect":
                    raise ConnectionError(f"Agent {agent_id} disconnected during turn")

                else:
                    logger.debug("Unexpected message in turn loop from agent %s: %s", agent_id, msg_type)

        finally:
            self._pending_turns.pop(key, None)
            self._agent_active_turn.pop(agent_id, None)

    async def _handle_tool_request(
        self,
        agent_id: UUID,
        data: dict,
        tool_executor: DebateToolExecutor | None,
        tool_context: ToolContext | None,
    ) -> None:
        """tool_request 처리 후 tool_result 전송."""
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", "")

        if tool_executor is None or tool_context is None:
            # 툴 실행기 미설정 — 에러 응답 반환
            result_msg = {
                "type": "tool_result",
                "tool_name": tool_name,
                "result": "",
                "error": "Tool execution is not available for this agent type",
            }
        else:
            tool_result = tool_executor.execute(tool_name, tool_input, tool_context)
            result_msg = {
                "type": "tool_result",
                "tool_name": tool_name,
                "result": tool_result.result,
                "error": tool_result.error,
            }
            logger.debug("Tool '%s' executed for agent %s: error=%s", tool_name, agent_id, tool_result.error)

        ws_cur = self._connections.get(agent_id)
        if ws_cur is not None:
            try:
                await ws_cur.send_json(result_msg)
            except Exception as exc:
                logger.warning("Failed to send tool_result to agent %s: %s", agent_id, exc)
        else:
            await self._publish_to_agent(agent_id, result_msg)

    async def handle_message(self, agent_id: UUID, data: dict) -> None:
        """수신 메시지 처리. 턴 관련 메시지는 활성 Queue에 전달."""
        msg_type = data.get("type")

        if msg_type in ("turn_response", "tool_request"):
            key = self._agent_active_turn.get(agent_id)
            if key:
                queue = self._pending_turns.get(key)
                if queue:
                    queue.put_nowait(data)
            else:
                logger.warning(
                    "Received %s from agent %s but no active turn registered", msg_type, agent_id
                )

        elif msg_type == "pong":
            await self._set_presence(agent_id, True)

        else:
            logger.debug("Unknown message type from agent %s: %s", agent_id, msg_type)

    async def send_match_ready(self, agent_id: UUID, msg: WSMatchReady) -> None:
        """match_ready 전송. 로컬 연결이 없으면 Redis pub/sub으로 다른 워커에 전달."""
        ws = self._connections.get(agent_id)
        if ws is not None:
            await ws.send_json(msg.model_dump(mode="json"))
        else:
            is_present = await self.check_presence(agent_id)
            if not is_present:
                raise ConnectionError(f"Agent {agent_id} is not connected")
            await self._publish_to_agent(agent_id, msg.model_dump(mode="json"))

    async def send_error(self, agent_id: UUID, message: str, code: str | None = None) -> None:
        """에이전트에게 에러 메시지를 전송한다. 전송 실패 시 조용히 무시.

        Args:
            agent_id: 대상 에이전트 UUID.
            message: 에러 메시지 문자열.
            code: 선택적 에러 코드.
        """
        ws = self._connections.get(agent_id)
        if ws is None:
            return
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "message": message, "code": code})

    async def send_ping(self, agent_id: UUID) -> None:
        """에이전트에게 ping을 전송한다. 실패 시 연결 해제 처리.

        Args:
            agent_id: 대상 에이전트 UUID.
        """
        ws = self._connections.get(agent_id)
        if ws is None:
            return
        try:
            await ws.send_json({"type": "ping"})
        except Exception:
            await self.disconnect(agent_id)

    async def _set_presence(self, agent_id: UUID, connected: bool) -> None:
        try:
            from app.core.redis import redis_client

            key = f"{_PRESENCE_PREFIX}{agent_id}:connected"
            if connected:
                await redis_client.setex(key, _PRESENCE_TTL, "1")
            else:
                await redis_client.delete(key)
        except Exception:
            logger.debug("Redis presence update failed for agent %s", agent_id)

    async def check_presence(self, agent_id: UUID) -> bool:
        """Redis 프레즌스로 접속 여부 확인 (메모리 + Redis 이중 체크)."""
        if self.is_connected(agent_id):
            return True
        try:
            from app.core.redis import redis_client

            key = f"{_PRESENCE_PREFIX}{agent_id}:connected"
            return await redis_client.exists(key) > 0
        except Exception:
            return False

    async def start_pubsub_listener(self) -> None:
        """Redis pub/sub 리스너 시작. 다른 인스턴스에서 온 메시지를 로컬 에이전트에 전달."""
        if self._pubsub_task is not None:
            return
        self._pubsub_task = asyncio.create_task(self._pubsub_loop_with_restart())
        logger.info("Started Redis pub/sub listener for agent messages")

    async def stop_pubsub_listener(self) -> None:
        """Redis pub/sub 리스너 중지."""
        if self._pubsub_task is not None:
            self._pubsub_task.cancel()
            self._pubsub_task = None
            logger.info("Stopped Redis pub/sub listener")

    async def _pubsub_loop_with_restart(self) -> None:
        """pub/sub 루프 — 예외로 종료 시 지수 백오프로 자동 재시작."""
        retry_delay = 1.0
        while True:
            try:
                await self._pubsub_loop()
                # 정상 종료 (CancelledError 이외의 return)
                break
            except asyncio.CancelledError:
                # 앱 종료 신호 — 재시작하지 않음
                break
            except Exception as exc:
                logger.warning(
                    "pub/sub loop crashed, restarting in %.1fs: %s",
                    retry_delay,
                    exc,
                )
                await asyncio.sleep(retry_delay)
                # 지수 백오프, 최대 60초
                retry_delay = min(retry_delay * 2, 60.0)

    async def _pubsub_loop(self) -> None:
        """Redis pub/sub 수신 루프."""
        try:
            from app.core.redis import redis_client

            pubsub = redis_client.pubsub()
            await pubsub.subscribe(_PUBSUB_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    import json

                    data = json.loads(message["data"])
                    target_agent_id = data.get("target_agent_id")
                    if target_agent_id:
                        from uuid import UUID as _UUID

                        agent_uuid = _UUID(target_agent_id)
                        ws = self._connections.get(agent_uuid)
                        if ws is not None:
                            payload = data.get("payload", {})
                            await ws.send_json(payload)
                        else:
                            # 로컬에 없으면 handle_message로 큐에 넣기 시도
                            payload = data.get("payload", {})
                            msg_type = payload.get("type")
                            if msg_type in ("turn_response", "tool_request"):
                                await self.handle_message(agent_uuid, payload)
                except Exception as exc:
                    logger.debug("pub/sub message handling error: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def _publish_to_agent(self, agent_id: UUID, payload: dict) -> None:
        """Redis pub/sub로 다른 인스턴스의 에이전트에 메시지 전달."""
        try:
            import json

            from app.core.redis import redis_client

            message = json.dumps({
                "target_agent_id": str(agent_id),
                "payload": payload,
            })
            await redis_client.publish(_PUBSUB_CHANNEL, message)
        except Exception:
            logger.debug("Failed to publish message to agent %s via Redis", agent_id)

    async def wait_for_connection(self, agent_id: UUID, wait_timeout: float) -> bool:
        """에이전트 접속 대기. wait_timeout 초 내에 접속하면 True.

        멀티 워커 환경에서 다른 워커에 연결된 에이전트도 Redis 프레즌스로 감지.
        지수 백오프(0.5→1→2→최대 5초)로 Redis 폴링 횟수를 줄인다.
        """
        deadline = asyncio.get_running_loop().time() + wait_timeout
        sleep_interval = 0.5
        while asyncio.get_running_loop().time() < deadline:
            if await self.check_presence(agent_id):
                return True
            remaining = deadline - asyncio.get_running_loop().time()
            await asyncio.sleep(min(sleep_interval, remaining, 5.0))
            sleep_interval = min(sleep_interval * 1.5, 5.0)
        return await self.check_presence(agent_id)
