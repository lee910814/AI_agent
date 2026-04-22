# DebateAutoMatcher

> 백그라운드 큐 폴링 및 플랫폼 에이전트 자동 매칭 데몬

**파일 경로:** `backend/app/services/debate/auto_matcher.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

FastAPI 서버 시작 시 백그라운드 루프를 시작하여 주기적으로 큐 상태를 점검한다.

**세 가지 역할:**
1. 만료된 큐 항목 정리 (`_purge_expired_queue_entries`)
2. 장시간 대기 큐 항목을 플랫폼 에이전트와 자동 매칭 (`_check_stale_entries`)
3. pending/waiting_agent/in_progress 상태로 멈춘 매치를 error로 처리 (`_check_stuck_matches`)

---

## 클래스: DebateAutoMatcher

싱글톤 패턴. `get_instance()`로 인스턴스를 얻는다.

### 라이프사이클

```python
# FastAPI lifespan 시작 시
DebateAutoMatcher.get_instance().start()

# FastAPI lifespan 종료 시
DebateAutoMatcher.get_instance().stop()
```

`start()` 호출 시 `asyncio.create_task`로 `_loop()`를 백그라운드 태스크로 시작한다.

### `_loop()` 실행 순서

```
서버 시작 후 즉시 1회 실행 (잔류 상태 초기화):
  1. _purge_expired_queue_entries()
  2. _check_stale_entries()
  3. _check_stuck_matches()

이후 debate_auto_match_check_interval (기본 10초) 주기로 반복:
  1. _purge_expired_queue_entries()
  2. _check_stale_entries()
  3. _check_stuck_matches()
```

---

## 내부 메서드

### `_check_stuck_matches()`

장시간 멈춘 매치를 `error` 상태로 전환한다.

| 상태 | 기준 타임스탬프 | 타임아웃 설정 키 |
|---|---|---|
| `pending` / `waiting_agent` | `created_at` | `debate_pending_timeout_seconds` |
| `in_progress` | `started_at` | `debate_inprogress_timeout_seconds` |

서버 비정상 종료 후 in_progress로 남은 매치 처리에 사용된다.

### `_purge_expired_queue_entries()`

`DebateMatchQueue.expires_at <= now`인 항목을 삭제하고 `timeout` SSE 이벤트를 발행한다.

- `SELECT ... FOR UPDATE SKIP LOCKED`으로 다른 태스크와 동시 처리 방지
- 삭제 전 `publish_queue_event(topic_id, agent_id, "timeout", {"reason": "queue_expired"})` 발행

### `_check_stale_entries()`

`DebateMatchQueue.joined_at < cutoff`인 항목을 플랫폼 에이전트와 자동 매칭한다.

- `cutoff = now - debate_queue_timeout_seconds`
- `SELECT ... FOR UPDATE SKIP LOCKED`으로 다른 태스크와 충돌 방지
- 플랫폼 에이전트가 없으면 `publish_queue_event(..., "timeout", {"reason": "no_platform_agents"})` 발행

### `_on_debate_task_done(task: asyncio.Task)`

`run_debate` 백그라운드 태스크 완료 콜백. 태스크에서 예외가 발생했을 때 `capture_exception()`으로 Sentry에 전송한다. 태스크 취소(`cancelled()`) 또는 예외 없음이면 무시한다.

### `_auto_match_with_platform_agent(db, entry)`

큐 항목에 대한 Redis 락을 획득한 뒤 `_do_auto_match()`를 호출하는 동시성 보호 래퍼다.

- 락 키: `match_lock:{topic_id}:{agent_id}` (Redis SETNX, TTL 30초)
- 락 획득 실패 시 즉시 `return` — 다른 태스크가 이미 처리 중임을 의미
- 락 획득 성공 시 `_do_auto_match()` 실행 후 `finally`에서 락 해제

### `_do_auto_match(db, entry)`

실제 매칭 로직. `_auto_match_with_platform_agent()` 내부의 Redis 락 범위 안에서 호출된다.

```
1. 큐 항목 재확인 (FOR UPDATE SKIP LOCKED) — 다른 태스크가 이미 처리했으면 return
2. is_platform=True, is_active=True, owner_id != entry.user_id인 에이전트 random() 선택
3. 플랫폼 에이전트 없으면 publish_queue_event(..., "timeout", {"reason": "no_platform_agents"}) 후 return
4. 각 에이전트 최신 버전(get_latest_version) 조회
5. DebateMatch 생성 (status="pending")
6. 큐 엔트리 삭제
7. DB 커밋
8. publish_queue_event(..., "matched", {"match_id": ..., "auto_matched": True})
9. asyncio.create_task(run_debate(match_id)) + 콜백 등록(_debate_tasks 관리, _on_debate_task_done)
```

---

## 데이터 흐름

```
FastAPI lifespan
  → DebateAutoMatcher.start()
  → _loop() (백그라운드 태스크)
      → 주기 실행
          ↓
          _purge_expired_queue_entries()
            → DebateMatchQueue WHERE expires_at <= now
            → DELETE + publish_queue_event("timeout")
          ↓
          _check_stale_entries()
            → DebateMatchQueue WHERE joined_at < cutoff
            → _auto_match_with_platform_agent()  (Redis 락 획득)
                → _do_auto_match()
                    → 큐 항목 재확인 (FOR UPDATE SKIP LOCKED)
                    → DebateAgent WHERE is_platform=True RANDOM
                    → DebateMatch INSERT
                    → DebateMatchQueue DELETE
                    → publish_queue_event("matched")
                    → asyncio.create_task(run_debate(match_id))
                → Redis 락 해제
          ↓
          _check_stuck_matches()
            → DebateMatch WHERE status IN ('pending','waiting_agent') AND created_at < cutoff
            → UPDATE status='error'
            → DebateMatch WHERE status='in_progress' AND started_at < cutoff
            → UPDATE status='error', finished_at=now
```

---

## 관련 설정값 (`config.py`)

| 설정 키 | 기본값 | 설명 |
|---|---|---|
| `debate_auto_match_check_interval` | `10` | 폴링 주기 (초) |
| `debate_queue_timeout_seconds` | `120` | 자동 매칭 대기 시간 (초) |
| `debate_pending_timeout_seconds` | 설정 참조 | pending/waiting_agent 타임아웃 (초) |
| `debate_inprogress_timeout_seconds` | 설정 참조 | in_progress 타임아웃 (초) |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `DebateMatchQueue` | `app.models.debate_match` | 큐 항목 조회·삭제 |
| `DebateMatch` | `app.models.debate_match` | 매치 생성·상태 업데이트 |
| `DebateAgent` | `app.models.debate_agent` | 플랫폼 에이전트 조회 |
| `get_latest_version` | `app.services.debate.agent_service` | 에이전트 최신 버전 조회 |
| `publish_queue_event` | `app.services.debate.broadcast` | 큐 SSE 이벤트 발행 |
| `run_debate` | `app.services.debate.engine` | 토론 엔진 시작 |
| `settings` | `app.core.config` | 타임아웃, 폴링 주기 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.1 | `_on_debate_task_done()` 콜백 메서드 추가. `_auto_match_with_platform_agent()`의 Redis 락 래퍼 역할 명시. `_do_auto_match()` 내부 메서드 및 실제 매칭 9단계 흐름 추가. 데이터 흐름 다이어그램 Redis 락 구조 반영 |
| 2026-03-17 | v1.0 | 신규 작성. `auto_matcher.py` 분리 반영. matching_service.py에서 분리된 백그라운드 데몬 구조 문서화 |
