# broadcast

> Redis Pub/Sub 기반 SSE 브로드캐스트 — 매치 관전 이벤트와 매칭 큐 상태 이벤트를 통합 관리하는 모듈

**파일 경로:** `backend/app/services/debate/broadcast.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

두 종류의 실시간 스트림을 담당한다.

- **매치 관전 채널** — 토론 엔진이 발행하는 턴·판정·종료 이벤트를 관전 중인 사용자에게 SSE로 전달. Redis Set으로 관전자 수를 추적하며 중복 카운트를 방지한다.
- **매칭 큐 채널** — 큐 대기자에게 상대 입장, 카운트다운 시작, 매칭 완료, 타임아웃 이벤트를 SSE로 전달.

두 채널은 공통 폴링 루프(`_poll_pubsub`)를 공유하므로 heartbeat·terminal event 처리 로직이 단일 코드베이스에 유지된다.

---

## 매치 채널 이벤트 목록 (`debate:match:{match_id}`)

| 이벤트 | 발행 시점 | 주요 페이로드 키 |
|---|---|---|
| `started` | 매치 시작 | `match_id` |
| `waiting_agent` | 로컬 에이전트 접속 대기 중 | `match_id` |
| `turn` | 에이전트 발언 완료 | `turn_number`, `speaker`, `claim`, `evidence`, `penalties`, `is_blocked` |
| `turn_review` | LLM 검토 완료 | `turn_number`, `speaker`, `logic_score`, `violations`, `feedback`, `blocked` |
| `turn_slot` | 멀티에이전트 슬롯 발언 (슬롯 레이블 보완용) | `speaker`, `turn_number` |
| `series_update` | 승급전/강등전 상태 변경 | `series_id`, `agent_id`, `series_type`, `status` |
| `finished` | 매치 완료 | `winner_id`, `score_a`, `score_b`, `elo_a_before/after`, `elo_b_before/after` |
| `forfeit` | 몰수패 | `forfeited_agent_id`, `winner_agent_id` |
| `credit_insufficient` | 크레딧 부족으로 매치 중단 | `agent_id`, `agent_name`, `required` |
| `match_void` | 기술 장애 무효화 | `reason` |
| `error` | 엔진 오류 | `message` |

> `_MATCH_TERMINAL_EVENTS` = `{"finished", "error", "forfeit"}` — 이 이벤트 수신 시 SSE 스트림 종료.
> `credit_insufficient`, `match_void`를 수신한 클라이언트는 즉시 매치 상태를 재조회해야 한다.

---

## 주요 상수

| 상수 | 타입 | 값 / 설명 |
|---|---|---|
| `_TERMINAL_EVENTS` | `set[str]` | `{"matched", "timeout", "cancelled"}` — 큐 채널 스트림 종료 트리거 이벤트 |
| `_MATCH_TERMINAL_EVENTS` | `set[str]` | `{"finished", "error", "forfeit"}` — 매치 채널 스트림 종료 트리거 이벤트 |

---

## 모듈 수준 함수

### 채널명 생성 (내부)

#### `_channel(match_id: str) -> str`

`"debate:match:{match_id}"` 형태의 Redis 채널명을 반환한다. `publish_event`와 `subscribe`에서 공통으로 사용한다.

#### `_queue_channel(topic_id: str, agent_id: str) -> str`

`"debate:queue:{topic_id}:{agent_id}"` 형태의 Redis 채널명을 반환한다. `publish_queue_event`와 `subscribe_queue`에서 공통으로 사용한다.

---

### 공통 폴링 루프 (내부)

#### `_poll_pubsub(pubsub, terminal_events: set[str], deadline: float) -> AsyncGenerator[str, None]`

Redis pub/sub 메시지를 SSE 형식(`data: ...\n\n`)으로 yield하는 공통 내부 루프다.

- 0.05s 즉시 폴링 후 메시지 없으면 2.0s 블로킹 대기 순으로 처리해 레이턴시와 CPU 낭비를 함께 억제한다.
- `terminal_events`에 속한 이벤트를 수신하면 즉시 `return`하여 generator를 종료한다.
- `deadline`을 초과하면 루프를 빠져나가 호출자에게 타임아웃 처리를 위임한다.
- 메시지가 없는 슬롯에는 `": heartbeat\n\n"`을 yield하여 연결을 유지한다.
- JSON 파싱 오류 발생 시 `logger.warning`만 남기고 폴링을 계속한다.

---

### 매치 관전 채널

#### `publish_event(match_id: str, event_type: str, data: dict) -> None`

`debate:match:{match_id}` 채널에 이벤트를 발행한다. 공유 `redis_client`를 사용하므로 턴 루프에서 반복 호출해도 연결 생성 오버헤드가 없다.

페이로드 형식:
```json
{"event": "<event_type>", "data": {...}}
```

#### `subscribe(match_id: str, user_id: str, max_wait_seconds: int = 600) -> AsyncGenerator[str, None]`

매치 채널을 구독하고 SSE 형식 문자열을 yield한다.

- 구독 시작 시 `SADD debate:viewers:{match_id} {user_id}` + `EXPIRE 3600` 으로 관전자를 등록한다. Redis Set을 사용하므로 동일 사용자가 탭을 새로고침해도 중복 카운트되지 않는다.
- `_MATCH_TERMINAL_EVENTS`(`finished`, `error`, `forfeit`) 수신 또는 `max_wait_seconds` 초과 시 스트림을 종료한다.
- 타임아웃 시 `{"event": "error", "data": {"message": "Stream timeout: match may have failed"}}` 이벤트를 발행하여 클라이언트가 `fetchMatch`로 상태를 갱신하도록 유도한다.
- `finally` 블록에서 `SREM`으로 관전자를 제거하고 pubsub 연결을 정리한다.

---

### 매칭 큐 채널

#### `publish_queue_event(topic_id: str, agent_id: str, event_type: str, data: dict) -> None`

`debate:queue:{topic_id}:{agent_id}` 채널에 큐 이벤트를 발행한다. `publish_event`와 동일하게 공유 `redis_client`를 사용한다.

- `topic_id` 또는 `agent_id`가 `None`이면 `logger.warning` 후 발행을 건너뛴다 (None 가드).
- Redis 발행 중 예외가 발생해도 내부에서 처리하고 호출자에게 전파하지 않는다 (best-effort). DB 커밋 이후에 호출되므로 실패해도 큐 등록/매치 생성 상태는 유지된다.

#### `subscribe_queue(topic_id: str, agent_id: str, max_wait_seconds: int = 120) -> AsyncGenerator[str, None]`

큐 채널을 구독하고 SSE 형식 문자열을 yield한다.

- `_TERMINAL_EVENTS`(`matched`, `timeout`, `cancelled`) 수신 또는 `max_wait_seconds`(기본 120초) 초과 시 스트림을 종료한다.
- 타임아웃 시 `{"event": "timeout", "data": {"reason": "queue_timeout"}}` 이벤트를 발행한다.
- `finally` 블록에서 pubsub 연결을 정리한다.

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `redis_client` | `app.core.redis` | 이벤트 발행 (PUBLISH) 및 관전자 Set 조작 (SADD·SREM·EXPIRE) |
| `pubsub_client` | `app.core.redis` | 구독 연결 풀 (pubsub 객체 생성) |

---

## 호출 흐름

### 매치 관전 흐름

```
services/debate/engine.py
  → publish_event(match_id, "turn", {...})       # 매 턴 완료 시
  → publish_event(match_id, "turn_review", {...}) # 턴 검토 결과
  → publish_event(match_id, "finished", {...})   # 매치 종료

api/debate_matches.py (GET /matches/{id}/stream)
  → subscribe(match_id, user_id)
      → pubsub_client.pubsub().subscribe("debate:match:{match_id}")
      → SADD debate:viewers:{match_id} {user_id}
      → _poll_pubsub(pubsub, _MATCH_TERMINAL_EVENTS, deadline)
          → yield "data: {...}\n\n"  (턴/종료 이벤트)
          → yield ": heartbeat\n\n"  (메시지 없는 슬롯)
      → [finished 수신] generator 종료
      → finally: SREM, pubsub.aclose()
```

### 매칭 큐 흐름

```
services/debate/matching_service.py
  → publish_queue_event(topic_id, agent_id, "opponent_joined", {...})
  → publish_queue_event(topic_id, agent_id, "countdown_started", {...})
  → publish_queue_event(topic_id, agent_id, "matched", {...})

api/debate_topics.py (GET /topics/{id}/queue/stream)
  → subscribe_queue(topic_id, agent_id)
      → pubsub_client.pubsub().subscribe("debate:queue:{topic_id}:{agent_id}")
      → _poll_pubsub(pubsub, _TERMINAL_EVENTS, deadline)
          → yield "data: {...}\n\n"  (큐 이벤트)
          → yield ": heartbeat\n\n"
      → [matched 수신] generator 종료
      → finally: pubsub.aclose()
```

### Redis 채널 구조

| 채널 패턴 | 용도 |
|---|---|
| `debate:match:{match_id}` | 매치 관전자용 이벤트 스트림 |
| `debate:queue:{topic_id}:{agent_id}` | 큐 대기자별 이벤트 스트림 |
| `debate:viewers:{match_id}` | 관전자 수 추적 (Redis Set, TTL 3600s) |

---

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| 관전자 SADD/SREM Redis 오류 | `logger.warning` 후 토론 중단 없이 계속 진행 |
| `_poll_pubsub` JSON 파싱 오류 | `logger.warning` 후 다음 메시지 폴링 계속 |
| `subscribe` 타임아웃 (`max_wait_seconds` 초과) | `error` 이벤트 발행 + `logger.warning` 후 generator 종료 |
| `subscribe_queue` 타임아웃 | `timeout` 이벤트 발행 + `logger.warning` 후 generator 종료 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | `publish_queue_event()`의 None 가드 로직 및 best-effort 예외 처리 설명 추가 |
| 2026-03-17 | 매치 채널 이벤트 목록 추가. `waiting_agent`, `credit_insufficient`, `match_void`, `series_update`, `turn_slot` 이벤트 문서화 |
| 2026-03-12 | 레퍼런스 형식에 맞춰 전면 재작성. 모듈 수준 함수 섹션으로 구조 재편, 호출 흐름 두 시나리오로 확장, Redis 채널 구조 표 추가 |
| 2026-03-11 | `services/debate/` 하위로 이동, 실제 코드 기반으로 초기 재작성 |
