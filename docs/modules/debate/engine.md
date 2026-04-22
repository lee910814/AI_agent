# DebateEngine

> 토론 매치 실행 오케스트레이터 (엔티티 로드 + 포맷 dispatch + finalize)

**파일 경로:** `backend/app/services/debate/engine.py`
**최종 수정일:** 2026-03-17

---

## 모듈 목적

`run_debate(match_id)` 진입점을 제공하고, 내부적으로 `DebateEngine` 클래스를 통해 매치 실행의 전 과정을 조율한다.

> **리팩토링 이력 (3a715c2):** 구버전 1716줄 단일 파일에서 342줄 오케스트레이터로 축소됨. 턴 루프는 `debate_formats.py`, 단일 턴 실행은 `turn_executor.py`, 판정은 `judge.py`, 후처리는 `finalizer.py`로 분리됨.

---

## `run_debate(match_id: str) -> None`

매치 실행 진입점. FastAPI 백그라운드 태스크에서 `asyncio.create_task(run_debate(match_id))`로 호출된다.

```
1. 별도 세션으로 매치 시작 알림 (NotificationService.notify_match_event("match_started"))
2. DebateEngine(db).run(match_id) 실행
3. 정상 완료 시: 별도 세션으로 매치 완료 알림 ("match_finished")
```

**예외 처리:**

| 예외 | 처리 방식 |
|---|---|
| `CreditInsufficientError` | credit_insufficient SSE 이미 발행됨 — error SSE 재발행 생략, DB에 status=error 기록 |
| `CancelledError` | `asyncio.shield`로 DB rollback + status=error 기록 + error SSE 발행 후 재발생 |
| `Exception` | DB rollback + status=error + error SSE 발행 |

---

## 클래스: DebateEngine

### `run(match_id: str) -> None`

실행 순서:

```
1. _load_entities(match_id)      — match/topic/agents/versions 병렬 조회
2. _deduct_credits(...)          — 플랫폼 크레딧 선차감
3. _wait_for_local_agents(...)   — 로컬 에이전트 WebSocket 접속 대기
4. (match.status == "forfeit이면 return")
5. status = "in_progress", started SSE 발행
6. _run_with_client(...)         — InferenceClient 공유 컨텍스트에서 포맷 실행
```

### `_load_entities(match_id) -> tuple`

match → topic + agents (병렬 gather) → versions 순으로 조회. 하나라도 없으면 `ValueError`.

### `_deduct_credits(match, topic, agent_a, agent_b)`

`credit_system_enabled=True` 시 `use_platform_credits=True` 에이전트 소유자의 크레딧을 선차감한다.

```python
required = math.ceil(max_turns × turn_token_limit × 1.5 × credit_per_1k / 1000)
# UPDATE users SET credit_balance = credit_balance - required
# WHERE id = owner_id AND credit_balance >= required
```

잔액 부족 시 `credit_insufficient` SSE 발행 후 `CreditInsufficientError` raise.

### `_wait_for_local_agents(match, topic, agent_a, agent_b)`

`provider == "local"`인 에이전트가 있으면 WebSocket 접속을 대기한다.

- 로컬 에이전트가 여럿이면 `asyncio.gather`로 병렬 대기 (순차 시 최대 N×timeout 낭비 방지)
- 타임아웃: `debate_agent_connect_timeout` (툴 사용 에이전트는 `debate_agent_connect_timeout_tool`)
- 재시도: `debate_agent_connect_retries` 횟수
- 접속 실패 시: `ForfeitHandler.handle_disconnect(match, agent, winner_agent, side)`

### `_deduct_credits` 크레딧 산정 함수

```python
def _calculate_required_credits(agent, models_map, max_turns, turn_token_limit) -> int:
    # 예상 토큰 = max_turns × turn_token_limit × 1.5 (입력 누적 버퍼)
    # 리뷰/판정 토큰은 포함하지 않음
```

순수 함수로 추출되어 있어 독립 테스트 가능.

### `_void_match(db, match, reason)`

기술 장애로 매치 무효화. `status="error"`, `error_reason=reason`, `match_void` SSE 발행.

### `_refund_credits(db, match)`

`match.credits_deducted`를 두 참가자에게 균등 환불. `use_platform_credits=True` 에이전트 소유자에게만.

### `_run_with_client(client, match, topic, ...)`

포맷별 분기 실행:

```python
match_format = getattr(match, "format", "1v1")
runner = get_format_runner(match_format)  # debate_formats.py

# 1v1
result = await runner(executor, orchestrator, db, match, topic,
    agent_a, agent_b, version_a, version_b, api_key_a, api_key_b,
    model_cache, usage_batch, parallel=orchestrator.optimized)

# 2v2/3v3
result = await runner(executor, orchestrator, db, match, topic,
    agent_a, agent_b, model_cache, usage_batch)
```

Before the turn loop starts, `DebateJudge.generate_intro(...)` is called first.
The engine then publishes a `judge_intro` SSE event (welcome + short topic briefing).
After that intro is sent, agent turns begin.

> **SSE 예외 격리 (2026-03-24):** `judge_intro` SSE 발행은 try/except로 보호된다. Redis 장애 등으로 SSE가 실패해도 매치 실행은 계속된다.

**예외 분기:**
- `MatchVoidError` → `_void_match` + `_refund_credits` → return
- `ForfeitError` → `ForfeitHandler.handle_retry_exhaustion(match, agent_a, agent_b, forfeited_speaker)` → return
- 정상 완료 → `DebateJudge.judge(...)` → `MatchFinalizer.finalize(...)`

---

## 하위 호환 래퍼

테스트 코드가 engine 모듈에서 직접 import하는 경로를 유지하기 위해 래퍼 함수들이 있다.

| 래퍼 함수 | 실제 구현 |
|---|---|
| `_execute_turn_with_retry` | `TurnExecutor.execute_with_retry` 위임 |
| `_run_turn_loop` | `debate_formats.run_turns_1v1` 위임 |

향후 테스트가 실제 모듈 경로로 마이그레이션되면 제거 예정.

---

## 관련 설정값 (`config.py`)

| 설정 키 | 설명 |
|---|---|
| `debate_agent_connect_timeout` | 로컬 에이전트 접속 대기 시간 (초) |
| `debate_agent_connect_timeout_tool` | 툴 사용 에이전트 접속 대기 시간 (초) |
| `debate_agent_connect_retries` | 접속 재시도 횟수 |
| `credit_system_enabled` | 플랫폼 크레딧 시스템 활성화 |
| `debate_orchestrator_optimized` | 병렬 실행 활성화 (True → 1v1 parallel=True) |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `DebateOrchestrator` | `app.services.debate.orchestrator` | 턴 검토 |
| `DebateJudge` | `app.services.debate.judge` | 최종 판정 |
| `MatchFinalizer` | `app.services.debate.finalizer` | 매치 완료 후처리 |
| `TurnExecutor` | `app.services.debate.turn_executor` | 단일 턴 실행 |
| `ForfeitHandler` | `app.services.debate.forfeit` | 몰수패 처리 |
| `get_format_runner`, `run_turns_1v1`, `run_turns_multi` | `app.services.debate.debate_formats` | 포맷별 턴 루프 |
| `_resolve_api_key`, `calculate_elo`, `_build_messages` | `app.services.debate.helpers` | API 키 해결, ELO, 메시지 구성 |
| `publish_event` | `app.services.debate.broadcast` | SSE 이벤트 발행 |
| `WSConnectionManager` | `app.services.debate.ws_manager` | 로컬 에이전트 WebSocket |
| `InferenceClient` | `app.services.llm.inference_client` | LLM 호출 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v3.1 | `judge_intro` SSE 발행 try/except 보호 추가 — Redis 장애 시 매치 실행 계속 |
| 2026-03-17 | v3.0 | 클래스 기반 재설계 반영 (3a715c2). DebateEngine 클래스 구조 문서화, 하위 호환 래퍼 명시, 분리된 모듈(judge/finalizer/auto_matcher) 링크 |
| 2026-03-12 | v2.1 | 알림 훅 명시, 의존 모듈 추가 |
| 2026-03-11 | v2.0 | 실제 코드 기반 전면 재작성 |
