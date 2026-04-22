# matching_service

> 큐 등록·준비 완료 처리·자동 매칭을 담당하는 매칭 서비스 모듈

**파일 경로:** `backend/app/services/debate/matching_service.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

`DebateMatchingService` 하나만 포함한다.

- **`DebateMatchingService`** — 사용자 요청 기반 큐 등록(`join_queue`)과 준비 완료 처리(`ready_up`). 양쪽 에이전트가 모두 준비되면 `DebateMatch`를 생성하고 토론 엔진을 시작한다.

> 백그라운드 자동 매칭 데몬(`DebateAutoMatcher`)은 `auto_matcher.py`로 분리되어 있다. 상세 내용은 [`docs/modules/debate/auto_matcher.md`](auto_matcher.md)를 참조한다.

---

## 주요 상수

없음

---

## 클래스: DebateMatchingService

### 생성자

```python
def __init__(self, db: AsyncSession)
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `db` | `AsyncSession` | SQLAlchemy 비동기 세션. FastAPI `Depends(get_db)`로 주입 |

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `join_queue` | `(user: User, topic_id: str, agent_id: str, password: str \| None = None) -> dict` | 큐 등록. 토픽·에이전트·크레딧 10단계 순차 검증 후 `DebateMatchQueue` INSERT. 상대가 이미 대기 중이면 양방향 `opponent_joined` 이벤트 발행 |
| `ready_up` | `(user: User, topic_id: str, agent_id: str) -> dict` | 준비 완료 처리. PK 오름차순 일괄 잠금으로 ABBA 데드락 방지. 양쪽 모두 준비 시 `DebateMatch` 생성 및 토론 엔진 시작 |
| `_purge_expired_entries` | `() -> None` | 만료된 큐 항목 일괄 삭제. `join_queue` 진입 시 호출되는 내부 메서드 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `verify_password` | `app.core.auth` | 토픽 비밀번호 검증 |
| `settings` | `app.core.config` | 큐 타임아웃, 카운트다운, 자동 매칭 주기 등 설정값 |
| `async_session` | `app.core.database` | `DebateAutoMatcher` 내부 독립 세션 생성 |
| `QueueConflictError` | `app.core.exceptions` | 유저/에이전트 큐 중복 시 409 응답용 |
| `DebateAgent` | `app.models.debate_agent` | 에이전트 소유권·활성 상태·플랫폼 여부 확인 |
| `DebateMatch`, `DebateMatchQueue` | `app.models.debate_match` | 매치·큐 ORM 모델 |
| `DebateTopic` | `app.models.debate_topic` | 토픽 존재·상태 확인 |
| `User` | `app.models.user` | 크레딧 잔액 조회 |
| `get_latest_version` | `app.services.debate.agent_service` | 매치 생성 시 에이전트 버전 스냅샷 연결 |
| `publish_queue_event` | `app.services.debate.broadcast` | 큐 상태 변경 SSE 이벤트 발행 |
| `DebatePromotionService` | `app.services.debate.promotion_service` | 활성 시리즈 조회 → `match_type`/`series_id` 태깅 |
| `DebateSeasonService` | `app.services.debate.season_service` | 활성 시즌 조회 → `season_id` 태깅 |

---

## 호출 흐름

### join_queue 검증 순서

```
API 라우터 (POST /topics/{id}/queue)
  → DebateMatchingService.join_queue(user, topic_id, agent_id, password)
      1. DebateTopic 조회 → 미존재 시 ValueError, status != "open" 시 ValueError
      2. is_password_protected 이면 verify_password() → 불일치 시 ValueError
      3. 에이전트 소유권 조회 (admin/superadmin은 소유권 체크 우회)
         → 미존재/비소유 시 ValueError, is_active=False 시 ValueError
      4. API 키 검증: provider != "local" && !encrypted_api_key && !use_platform_credits
         → 플랫폼 fallback 키도 없으면 ValueError
      5. credit_system_enabled && debate_credit_cost > 0 && !encrypted_api_key
         → User.credit_balance < debate_credit_cost 이면 ValueError
      6. _purge_expired_entries() — 만료 항목 일괄 삭제
      7. 유저당 1개 큐 제한 (admin/superadmin 제외)
         → 기존 항목 있으면 QueueConflictError
      8. 에이전트 어느 토픽이든 이미 대기 중인지 확인
         → 같은 토픽: ValueError / 다른 토픽: QueueConflictError
      9. DebateMatchQueue INSERT + flush
         → IntegrityError(race condition) 시 rollback → ValueError
      10. 상대 존재 시 양방향 opponent_joined 이벤트 발행
      → 반환: {"status": "queued", "position": 1, "opponent_agent_id": ...}
```

### ready_up 매치 생성 흐름

```
API 라우터 (POST /topics/{id}/ready)
  → DebateMatchingService.ready_up(user, topic_id, agent_id)
      → 토픽 내 전체 큐 항목 PK 오름차순 WITH FOR UPDATE 일괄 잠금
        (ABBA 데드락 방지: 두 concurrent 트랜잭션이 동일 잠금 순서 보장)
      → my_entry 탐색 → 없으면 ValueError("Not in queue")
      → my_entry.is_ready = True 이미 True면 멱등 반환
      → opponent_entry 탐색
          ├─ [상대 미존재] commit → {"status": "ready", "waiting_for_opponent": True}
          ├─ [상대 미준비] commit
          │       → countdown_started 이벤트 양방향 발행
          │       → {"status": "ready", "countdown_started": True, ...}
          └─ [양쪽 모두 준비]
              → get_latest_version(my_agent), get_latest_version(opponent_agent)
              → DebateMatch(status="pending") INSERT
              → DebateSeasonService.get_active_season() → season_id 태깅
              → DebatePromotionService.get_active_series() × 2 → match_type/series_id 태깅
                (두 에이전트 모두 시리즈 중이면 첫 번째만 연결)
              → my_entry, opponent_entry 삭제 → commit
              → matched 이벤트 양방향 발행
              → asyncio.create_task(run_debate(match_id))
              → {"status": "matched", "match_id": ...}
```

> 백그라운드 자동 매칭 루프(`DebateAutoMatcher`) 흐름은 [`auto_matcher.md`](auto_matcher.md)를 참조한다.

---

## 에러 처리

| 상황 | 예외 | HTTP 변환 |
|---|---|---|
| 토픽 미존재 | `ValueError("Topic not found")` | 404 |
| 토픽 미개방 (`status != "open"`) | `ValueError("Topic is not open for matches")` | 400 |
| 토픽 비밀번호 불일치 | `ValueError("비밀번호가 올바르지 않습니다")` | 400 |
| 에이전트 미존재/비소유 | `ValueError("Agent not found or not owned by user")` | 404 |
| 에이전트 비활성 | `ValueError("Agent is not active")` | 400 |
| API 키 미설정 + 플랫폼 키 없음 | `ValueError("에이전트에 API 키가 설정되지 않았습니다...")` | 400 |
| 크레딧 부족 | `ValueError("크레딧이 부족합니다. 필요: N석, 현재: M석")` | 400 |
| 유저 큐 중복 (다른 에이전트로 대기 중) | `QueueConflictError` | 409 |
| 에이전트 큐 중복 (같은 토픽) | `ValueError("Agent already in queue for this topic")` | 400 |
| 에이전트 큐 중복 (다른 토픽) | `QueueConflictError` | 409 |
| INSERT race condition (`uq_debate_queue_topic_agent`) | `ValueError("Agent already in queue for this topic")` | 400 |
| ready_up 시 큐 미존재 | `ValueError("Not in queue")` | 400 |

예외 → HTTP 상태코드 변환은 `api/debate_topics.py` 라우터가 담당한다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | `DebateAutoMatcher` 클래스 섹션 제거 (`auto_matcher.py`로 분리됨). 모듈 목적 단일 클래스로 정정. 의존 모듈에서 `run_debate` 항목 제거 (실제 import 없음). `DebateAutoMatcher` 백그라운드 루프 호출 흐름 → `auto_matcher.md` 참조로 대체 |
| 2026-03-12 | 레퍼런스 형식에 맞춰 전면 재작성. 클래스 2개 분리 표기, join_queue 10단계 검증 흐름 상세화, DebateAutoMatcher 백그라운드 루프 흐름 추가, 에러 처리 표 확장 |
| 2026-03-11 | `services/debate/` 하위로 이동, 실제 코드 기반으로 초기 재작성 |
