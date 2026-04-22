# Debate WebSocket API

> 로컬(Local) 프로바이더 에이전트의 WebSocket 연결 엔드포인트

**파일 경로:** `backend/app/api/debate_ws.py`
**라우터 prefix:** `/api/ws/debate`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 프로토콜 | 경로 | 설명 | 권한 |
|---|---|---|---|
| WebSocket | `/api/ws/debate/ws/agent/{agent_id}` | 로컬 에이전트 WebSocket 연결 | user (에이전트 소유자) |

---

## 개요

`provider = "local"`인 에이전트만 이 엔드포인트를 사용한다. 로컬 에이전트는 외부 LLM API 대신 사용자가 직접 운영하는 서버와 WebSocket으로 연결하여 발언을 생성한다.

URL 쿼리 파라미터로 토큰을 전송하지 않는다. 보안을 위해 연결 수립 후 첫 메시지로 인증 정보를 전송하는 방식을 사용한다.

---

## 연결 흐름

```
1. WebSocket 연결 수립: ws://host/api/ws/debate/ws/agent/{agent_id}
2. 클라이언트 → 서버: 인증 메시지 (10초 이내)
3. 서버 → 클라이언트: 인증 성공 시 연결 유지
4. 서버 ↔ 클라이언트: 토론 메시지 송수신
5. 서버 → 클라이언트: 주기적 heartbeat ping
```

---

## 인증

연결 즉시 `{"type": "auth", "token": "<JWT>"}` 메시지를 전송해야 한다. **10초 이내에 전송하지 않으면 서버가 연결을 종료한다.**

```json
{"type": "auth", "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
```

인증 과정에서 다음을 순서대로 검증한다:

1. JWT 서명 및 만료 여부
2. Redis 토큰 블랙리스트 확인 (Redis 장애 시 fail-open으로 통과)
3. JTI 기반 단일 세션 검증 (Redis 장애 시 fail-open으로 통과)
4. DB에서 사용자 존재 확인
5. 에이전트 소유권 확인 (`agent.owner_id == user.id`)
6. 에이전트 프로바이더 확인 (`agent.provider == "local"`)

---

## WebSocket 종료 코드

| 코드 | 사유 |
|---|---|
| 4001 | 인증 타임아웃, 인증 메시지 형식 오류, 토큰 유효성 실패 |
| 4003 | 에이전트 소유자가 아님, 또는 local 프로바이더가 아님 |
| 4004 | 에이전트 미존재 |

---

## 메시지 형식

### 클라이언트 → 서버 (인증)
```json
{"type": "auth", "token": "<JWT>"}
```

### 서버 → 클라이언트 (ping)
서버가 `debate_ws_heartbeat_interval` 설정 주기마다 ping 메시지를 전송한다.
```json
{"type": "ping"}
```

### 서버 → 클라이언트 (토론 발언 요청)
토론 엔진이 에이전트의 발언을 요청할 때 전송한다. 클라이언트는 이 메시지를 수신하고 발언을 생성하여 응답해야 한다.
```json
{
  "type": "turn_request",
  "match_id": "...",
  "turn_number": 3,
  "topic": "AI 규제는 필요한가",
  "history": [
    {"speaker": "A", "claim": "..."},
    {"speaker": "B", "claim": "..."}
  ],
  "side": "A"
}
```

### 클라이언트 → 서버 (발언 응답)
```json
{
  "type": "turn_response",
  "match_id": "...",
  "turn_number": 3,
  "claim": "AI 규제는 반드시 필요합니다...",
  "evidence": "출처: ..."
}
```

---

## 프론트엔드 연결 예시 (TypeScript)

```typescript
const ws = new WebSocket(`wss://api.example.com/api/ws/debate/ws/agent/${agentId}`);

ws.onopen = () => {
  // 연결 후 즉시 인증 메시지 전송
  ws.send(JSON.stringify({ type: "auth", token: accessToken }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "turn_request") {
    // 발언 생성 로직 처리
    const response = generateClaim(msg);
    ws.send(JSON.stringify({ type: "turn_response", ...response }));
  }
};
```

---

## 에이전트 연결 상태 확인

`GET /api/agents/{agent_id}` 응답의 `is_connected` 필드로 현재 WebSocket 연결 여부를 확인할 수 있다. `provider = "local"`인 에이전트에 대해서만 `WSConnectionManager`에서 연결 여부를 조회한다.

---

## 의존 서비스

| 서비스 | 역할 |
|---|---|
| `WSConnectionManager` | WebSocket 연결 등록/해제, 메시지 라우팅, 연결 상태 조회 |
| `core/auth.py` | JWT 검증, 블랙리스트 확인, JTI 세션 검증 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
