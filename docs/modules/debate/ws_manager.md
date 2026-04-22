# WSConnectionManager

> 로컬 에이전트 WebSocket 연결 관리 싱글톤 — 턴 요청/응답·툴 중계·Redis 프레즌스·멀티 워커 지원

**파일 경로:** `backend/app/services/debate/ws_manager.py`
**최종 수정일:** 2026-03-12

---

## 모듈 목적

자체 WebSocket 클라이언트로 접속하는 로컬 에이전트의 연결 생명주기를 관리한다.

- **연결 관리** — JWT 인증 후 등록, stale 연결 자동 정리, 재연결 시 pending Queue 보존
- **턴 요청/응답** — `WSTurnRequest` 전송 후 `WSTurnResponse` 수신까지 툴 요청(0~N회)을 중계하는 루프 실행
- **툴 실행 중계** — `tool_request` 수신 시 `DebateToolExecutor`를 호출하고 `tool_result`를 에이전트로 전송
- **Redis 프레즌스** — 연결 상태를 `setex(key, 60, "1")`으로 공유해 멀티 워커 환경에서 에이전트 감지
- **멀티 워커 메시지** — 로컬에 없는 에이전트는 Redis pub/sub(`debate:agent:messages`)으로 다른 워커에 전달
- **pub/sub 리스너** — 앱 lifespan에서 시작·종료. 크래시 시 지수 백오프로 자동 재시작

---

## 주요 상수

| 상수 | 타입 | 값 / 설명 |
|---|---|---|
| `_PRESENCE_PREFIX` | `str` | `"debate:agent:"` — Redis 프레즌스 키 접두사 |
| `_PRESENCE_TTL` | `int` | `60` — 프레즌스 키 TTL(초). heartbeat 갱신 주기보다 충분히 길게 설정 |
| `_PUBSUB_CHANNEL` | `str` | `"debate:agent:messages"` — 멀티 워커 메시지 전달용 Redis pub/sub 채널 |

---

## 클래스: WSConnectionManager

싱글톤 패턴. `get_instance()`로만 접근한다.

### 생성자

```python
def __init__(self) -> None
```

직접 인스턴스화하지 않는다. `get_instance()` 클래스 메서드를 사용한다.

| 내부 속성 | 타입 | 설명 |
|---|---|---|
| `_connections` | `dict[UUID, WebSocket]` | agent_id → WebSocket 매핑 |
| `_pending_turns` | `dict[str, asyncio.Queue]` | `"{match_id}:{turn_number}:{speaker}"` → Queue 매핑 |
| `_agent_active_turn` | `dict[UUID, str]` | agent_id → 현재 활성 턴 key (툴 메시지 라우팅용) |
| `_pubsub_task` | `asyncio.Task \| None` | Redis pub/sub 리스너 백그라운드 태스크 |

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `get_instance` | `() -> WSConnectionManager` | 싱글톤 인스턴스 반환 (없으면 생성) |
| `connect` | `(agent_id: UUID, ws: WebSocket) -> None` | WebSocket 등록 + Redis 프레즌스 설정. 기존 stale 연결 정리 후 새 연결 등록. pending Queue는 보존 |
| `disconnect` | `(agent_id: UUID) -> None` | 연결 해제 + Redis 프레즌스 삭제 + 활성 Queue에 `_disconnect` 신호 전달 |
| `is_connected` | `(agent_id: UUID) -> bool` | 로컬 메모리 기준 연결 상태 확인 (`WebSocketState.CONNECTED` 체크) |
| `request_turn` | `(match_id: UUID, agent_id: UUID, request: WSTurnRequest, tool_executor: DebateToolExecutor \| None, tool_context: ToolContext \| None) -> WSTurnResponse` | 턴 요청 전송 + `turn_response` 수신까지 `tool_request` 처리 루프 실행. 타임아웃은 caller의 `asyncio.wait_for()` 담당 |
| `handle_message` | `(agent_id: UUID, data: dict) -> None` | 수신 메시지 처리. `turn_response`/`tool_request`는 활성 Queue에 전달. `pong`은 프레즌스 갱신 |
| `send_match_ready` | `(agent_id: UUID, msg: WSMatchReady) -> None` | `match_ready` 전송. 로컬 연결 없으면 Redis pub/sub으로 다른 워커에 전달 |
| `send_error` | `(agent_id: UUID, message: str, code: str \| None) -> None` | 에러 메시지 전송. 연결 없으면 무시. 전송 실패도 `contextlib.suppress`로 무시 |
| `send_ping` | `(agent_id: UUID) -> None` | ping 전송. 실패 시 `disconnect()` 호출 |
| `check_presence` | `(agent_id: UUID) -> bool` | 메모리 + Redis 이중 확인. 다른 워커에 연결된 에이전트도 감지 가능 |
| `wait_for_connection` | `(agent_id: UUID, wait_timeout: float) -> bool` | 에이전트 접속 대기. 지수 백오프(0.5 → 1 → 2 → 최대 5초) 폴링 |
| `start_pubsub_listener` | `() -> None` | Redis pub/sub 리스너 시작. 이미 실행 중이면 무시 |
| `stop_pubsub_listener` | `() -> None` | Redis pub/sub 리스너 태스크 취소 |
| `_cleanup_stale_connection` | `(agent_id: UUID, stale_ws: WebSocket) -> None` | stale WebSocket을 code=1012로 안전 종료. pending Queue는 보존 |
| `_handle_tool_request` | `(agent_id: UUID, data: dict, tool_executor: DebateToolExecutor \| None, tool_context: ToolContext \| None) -> None` | `tool_request` 처리 후 `tool_result` 메시지를 에이전트로 전송 |
| `_set_presence` | `(agent_id: UUID, connected: bool) -> None` | Redis 프레즌스 키 설정(`setex(key, 60, "1")`) 또는 삭제. 실패 시 `logger.debug`로 무시 |
| `_publish_to_agent` | `(agent_id: UUID, payload: dict) -> None` | `{"target_agent_id": str, "payload": dict}` 구조로 Redis pub/sub 발행 |
| `_pubsub_loop_with_restart` | `() -> None` | pub/sub 루프 래퍼. 예외 종료 시 지수 백오프(1 → 2 → … 최대 60초)로 자동 재시작. `CancelledError`는 재시작하지 않음 |
| `_pubsub_loop` | `() -> None` | Redis pub/sub 수신 루프. `target_agent_id` 기반으로 로컬 에이전트에 페이로드 전달 또는 `handle_message`로 라우팅 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `WebSocket`, `WebSocketState` | `starlette.websockets` | WebSocket 객체 및 연결 상태 확인 |
| `WSMatchReady`, `WSTurnRequest`, `WSTurnResponse` | `app.schemas.debate_ws` | WebSocket 메시지 스키마 |
| `DebateToolExecutor`, `ToolContext` | `app.services.debate.tool_executor` | 툴 실행기 및 문맥 타입 |
| `redis_client` | `app.core.redis` | Redis 프레즌스·pub/sub (지연 임포트) |

---

## 호출 흐름

### 턴 요청/응답 흐름

```
engine.py (_execute_turn, local 에이전트)
  → ws_manager.wait_for_connection(agent_id, timeout)   # 접속 대기
  → ws_manager.send_match_ready(agent_id, WSMatchReady)  # 매치 시작 알림
  → asyncio.wait_for(
        ws_manager.request_turn(
            match_id, agent_id, WSTurnRequest,
            tool_executor=DebateToolExecutor(),
            tool_context=ToolContext(...)
        ),
        timeout=turn_timeout
    )

request_turn 내부:
  1. key = "{match_id}:{turn_number}:{speaker}" 생성
  2. asyncio.Queue 생성, _pending_turns[key] 등록
  3. _agent_active_turn[agent_id] = key
  4. ws.send_json(WSTurnRequest) 또는 Redis pub/sub 발행
  5. 메시지 루프:
     ├─ "turn_response" → WSTurnResponse.model_validate(data) 반환
     ├─ "tool_request"  → _handle_tool_request() → tool_result 전송 → 루프 계속
     └─ "_disconnect"   → ConnectionError 발생
  6. finally: _pending_turns, _agent_active_turn 정리
```

### WebSocket 연결 수명주기

```
API 라우터 (api/debate_ws.py)
  → WSConnectionManager.get_instance()
  → connect(agent_id, ws)          # JWT 인증 성공 후 등록
  → handle_message(agent_id, data) # 수신 메시지 처리 루프 (무한)
  → disconnect(agent_id)           # 연결 종료 (정상/오류 모두)
```

### 앱 생명주기 연동

```
main.py (lifespan)
  → start_pubsub_listener()   # 앱 시작 시
  → stop_pubsub_listener()    # 앱 종료 시
```

### Redis 키 구조

| 키 패턴 | 용도 | TTL |
|---|---|---|
| `debate:agent:{agent_id}:connected` | 에이전트 프레즌스 (값 `"1"`) | 60초 |
| `debate:agent:messages` | 멀티 워커 메시지 pub/sub 채널 | 없음 |

---

## 에러 처리

| 상황 | 동작 |
|---|---|
| 로컬 연결 없고 Redis 프레즌스도 없음 | `ConnectionError` 발생 (`request_turn`, `send_match_ready`) |
| 에이전트가 턴 중 연결 해제 | `_disconnect` 신호 → Queue → `ConnectionError` 발생 |
| `send_json` 실패 (`_handle_tool_request`) | `logger.warning` 후 무시 |
| `send_error` 전송 실패 | `contextlib.suppress(Exception)`으로 무시 |
| `send_ping` 실패 | `disconnect(agent_id)` 호출 |
| Redis 프레즌스 업데이트 실패 | `logger.debug` 후 무시 |
| Redis pub/sub 메시지 파싱 오류 | `logger.debug` 후 해당 메시지 스킵 |
| pub/sub 루프 크래시 | `logger.warning` 후 지수 백오프(최대 60초)로 자동 재시작 |
| `turn_response` 역직렬화 실패 | `logger.warning` 후 루프 계속 (에이전트가 재전송 기다림) |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-12 | 레퍼런스 형식에 맞춰 전면 재작성. 내부 상태 속성을 생성자 섹션으로 통합, Redis 키 구조 표 추가, 호출 흐름 3개 시나리오로 확장, 에러 처리 행별 상세화 |
| 2026-03-11 | 실제 코드 기반으로 초기 재작성 |
