# topic_service

> 토론 토픽 CRUD, 목록 조회·정렬, 스케줄 기반 상태 자동 갱신을 담당하는 서비스 모듈

**파일 경로:** `backend/app/services/debate/topic_service.py`
**최종 수정일:** 2026-03-12

---

## 모듈 목적

`DebateTopicService` 단일 클래스로 구성되어 있다.

- **토픽 생성/조회/수정/삭제** — 일반 사용자와 관리자 각각의 권한 경로를 별도 메서드로 분리한다.
- **목록 조회** — 집계 서브쿼리로 `queue_count`·`match_count`를 한 번의 JOIN으로 조회하여 N+1을 방지하며, 4가지 정렬 기준을 지원한다.
- **스케줄 자동 동기화** — `list_topics()` 호출 시 `_sync_scheduled_topics()`가 자동 실행된다. Redis SET NX EX 패턴으로 멀티 워커 환경에서도 60초 이내 중복 실행을 방지한다.

---

## 주요 상수

| 상수 | 타입 | 값 / 설명 |
|---|---|---|
| `_TOPIC_SYNC_REDIS_KEY` | `str` | `"debate:topic_sync:last_at"` — 스케줄 동기화 분산 락 Redis 키 |
| `_TOPIC_SYNC_INTERVAL_SECS` | `int` | `60` — 스케줄 동기화 최소 실행 간격 (초). SET NX EX 값으로 사용 |

---

## 클래스: DebateTopicService

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
| `create_topic` | `(data: TopicCreate, user: User) -> DebateTopic` | 토픽 생성. 일반 사용자 일일 등록 한도 검사(`debate_daily_topic_limit`). `scheduled_start_at`이 미래이면 `"scheduled"`, 아니면 `"open"`. 비밀번호 지정 시 해싱 후 저장 |
| `get_topic` | `(topic_id: str) -> DebateTopic \| None` | ID로 단일 토픽 조회 |
| `list_topics` | `(status: str \| None, sort: str, page: int, page_size: int) -> tuple[list[dict], int]` | 토픽 목록 페이지네이션. 호출마다 `_sync_scheduled_topics()` 자동 실행. 집계 서브쿼리로 `queue_count`·`match_count` 포함 반환 |
| `update_topic` | `(topic_id: str, data: TopicUpdate) -> DebateTopic` | 관리자용 토픽 수정. 소유권 검사 없음 |
| `update_topic_by_user` | `(topic_id: UUID, user_id: UUID, payload: TopicUpdatePayload) -> DebateTopic` | 작성자 본인 수정. 미존재 시 `ValueError`, 소유권 불일치 시 `PermissionError` |
| `delete_topic` | `(topic_id: str) -> None` | 관리자용 토픽 삭제. 테스트 제외 매치가 하나라도 있으면 삭제 거부. 대기 큐 먼저 제거 후 삭제 |
| `delete_topic_by_user` | `(topic_id: UUID, user_id: UUID) -> None` | 작성자 본인 삭제. 소유권 + 진행 중(`in_progress`) 매치 여부만 검사 (완료 매치는 허용) |
| `count_queue` | `(topic_id) -> int` | 현재 대기 큐 항목 수 반환 |
| `count_matches` | `(topic_id) -> int` | `is_test=False` 기준 전체 매치 수 반환 |
| `_sync_scheduled_topics` | `() -> None` | 스케줄 기반 status 자동 갱신. Redis 분산 락으로 60초 이내 재실행 방지. Redis 장애 시 락 없이 실행(폴백) |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `get_password_hash` | `app.core.auth` | 토픽 비밀번호 bcrypt 해싱 |
| `get_redis` | `app.core.redis` | 스케줄 동기화 분산 락 (SET NX EX) |
| `settings` | `app.core.config` | `debate_daily_topic_limit` 읽기 (지연 임포트, `create_topic` 내부) |
| `DebateMatch`, `DebateMatchQueue` | `app.models.debate_match` | 매치 수 집계 및 큐 정리 |
| `DebateTopic` | `app.models.debate_topic` | 토픽 ORM 모델 |
| `User` | `app.models.user` | 작성자 닉네임 JOIN 조회 |
| `TopicCreate`, `TopicUpdate`, `TopicUpdatePayload` | `app.schemas.debate_topic` | 입력 스키마 |

---

## 호출 흐름

### 토픽 생성 흐름

```
API 라우터 (POST /api/topics)
  → DebateTopicService.create_topic(data, user)
      → [is_admin=False] SELECT count WHERE created_by=user.id AND created_at >= today
          → today_count >= debate_daily_topic_limit 이면 ValueError
      → scheduled_start_at > now 이면 status = "scheduled", 아니면 "open"
      → data.password 있으면 get_password_hash() → is_password_protected = True
      → DebateTopic INSERT → commit → refresh → 반환
```

### 목록 조회 흐름

```
API 라우터 (GET /api/topics)
  → DebateTopicService.list_topics(status, sort, page, page_size)
      → _sync_scheduled_topics()
          → get_redis() → SET NX EX _TOPIC_SYNC_REDIS_KEY 60
              → [이미 키 있음] return (다른 워커가 처리 중)
              → [키 없음 또는 Redis 장애]
                  → UPDATE scheduled AND scheduled_start_at <= now → open
                  → UPDATE open/in_progress AND scheduled_end_at <= now → closed
                  → commit
      → queue_subq: SELECT topic_id, count(id) FROM debate_match_queues GROUP BY topic_id
      → match_subq: SELECT topic_id, count(id) FROM debate_matches WHERE is_test=False GROUP BY topic_id
      → SELECT DebateTopic + User.nickname + coalesce(q_cnt) + coalesce(m_cnt)
          OUTER JOIN queue_subq, match_subq, User
      → [sort = "popular_week"]
          → popular_subq: 최근 7일 debate_matches GROUP BY topic_id
          → ORDER BY weekly_cnt DESC, created_at DESC
      → [sort = "queue"] ORDER BY q_cnt DESC, created_at DESC
      → [sort = "matches"] ORDER BY m_cnt DESC, created_at DESC
      → [sort = "recent"] ORDER BY created_at DESC
      → OFFSET / LIMIT → 결과 dict 목록 조합 → (items, total) 반환
```

### 삭제 권한 분기

```
관리자 (DELETE /api/admin/debate/topics/{id})
  → DebateTopicService.delete_topic(topic_id)
      → count_matches(topic_id) > 0 이면 ValueError (완료 매치 포함)
      → DELETE debate_match_queues WHERE topic_id
      → DELETE debate_topics WHERE id

사용자 (DELETE /api/topics/{id})
  → DebateTopicService.delete_topic_by_user(topic_id, user_id)
      → topic.created_by != user_id 이면 PermissionError
      → count(debate_matches WHERE status="in_progress") > 0 이면 ValueError
      → DELETE debate_match_queues WHERE topic_id
      → DELETE debate_topics WHERE id
```

### list_topics sort 옵션

| 값 | 정렬 기준 |
|---|---|
| `recent` (기본값) | `created_at DESC` |
| `popular_week` | 최근 7일 매치 수 DESC, 동점 시 `created_at DESC` |
| `queue` | 현재 큐 대기 수 DESC, 동점 시 `created_at DESC` |
| `matches` | 전체 매치 수 DESC, 동점 시 `created_at DESC` |

### `_sync_scheduled_topics` 상태 전환 규칙

| 조건 | 전환 |
|---|---|
| `status = "scheduled"` AND `scheduled_start_at <= now` | `"open"` |
| `status IN ("open", "in_progress")` AND `scheduled_end_at IS NOT NULL` AND `scheduled_end_at <= now` | `"closed"` |

---

## 에러 처리

| 상황 | 예외 | HTTP 변환 |
|---|---|---|
| 일일 등록 한도 초과 | `ValueError("일일 토론 주제 등록 한도({N}개)에 도달했습니다. 내일 다시 시도하세요.")` | 400 |
| 토픽 미존재 | `ValueError("Topic not found")` | 404 |
| 소유권 불일치 | `PermissionError("Not the topic creator")` | 403 |
| 관리자 삭제 시 매치 있음 | `ValueError("진행된 매치가 {N}개 있어 삭제할 수 없습니다. 종료 처리 후 매치가 없을 때 삭제 가능합니다.")` | 409 |
| 사용자 삭제 시 진행 중 매치 있음 | `ValueError("진행 중인 매치가 {N}개 있어 삭제할 수 없습니다.")` | 409 |

예외 → HTTP 상태코드 변환은 `api/debate_topics.py` 및 `api/admin/debate/topics.py` 라우터가 담당한다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-12 | 레퍼런스 형식에 맞춰 전면 재작성. 클래스/생성자/메서드 표 구조로 재편, 호출 흐름 3개 시나리오 상세화, sort 옵션 표 및 상태 전환 규칙 표 추가, 에러 처리 표 실제 메시지로 상세화 |
| 2026-03-11 | `services/debate/` 하위로 이동, 실제 코드 기반으로 초기 재작성 |
