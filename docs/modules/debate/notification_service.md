# NotificationService

> 매치 이벤트·예측투표 결과·신규 팔로워 알림을 생성하고 사용자별로 조회하는 서비스 계층

**파일 경로:** `backend/app/services/notification_service.py`
**최종 수정일:** 2026-03-24

---

## 모듈 목적

`NotificationService`는 플랫폼 내 주요 이벤트 발생 시 사용자에게 알림을 전달하는 역할을 한다.

- **알림 생성** — 단건(`create`) 및 N건 일괄(`create_bulk`) 생성
- **알림 조회** — 페이지네이션, 미읽기 필터, 단일 집계 쿼리로 total/unread_count 동시 반환
- **읽음 처리** — 단건 및 전체 읽음 처리 (소유권 검증 포함)
- **도메인 알림** — 매치 이벤트(`notify_match_event`), 예측투표 결과(`notify_prediction_result`), 신규 팔로워(`notify_new_follower`) 3가지 유형의 고수준 알림 생성 메서드 제공

`create_bulk`는 DB 오류 발생 시 예외를 전파하지 않으므로, 알림 실패가 토론 엔진이나 매치 서비스의 핵심 트랜잭션을 중단하지 않는다.

---

## 주요 상수

없음

---

## 클래스: NotificationService

### 생성자

```python
def __init__(self, db: AsyncSession)
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `db` | `AsyncSession` | SQLAlchemy 비동기 세션. FastAPI `Depends(get_db)` 또는 `async_session()` 별도 생성으로 주입 |

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `create` | `(user_id: UUID, type: str, title: str, body: str \| None, link: str \| None) -> UserNotification` | 알림 1건 생성 후 flush |
| `create_bulk` | `(notifications: list[dict]) -> None` | 알림 N건 일괄 생성. 실패 시 rollback 후 로깅만 수행하며 예외 전파하지 않음 |
| `get_list` | `(user_id: UUID, offset: int, limit: int, unread_only: bool = False) -> tuple[list[UserNotification], int, int]` | 알림 목록(`created_at DESC`) + (total, unread_count) 반환. 단일 집계 쿼리로 이중 COUNT 제거 |
| `get_unread_count` | `(user_id: UUID) -> int` | 미읽기 알림 수 반환 |
| `mark_read` | `(notification_id: UUID, user_id: UUID) -> None` | 단건 읽음 처리. 미존재 시 `ValueError`, 소유권 불일치 시 `PermissionError` |
| `mark_all_read` | `(user_id: UUID) -> int` | 전체 미읽기 알림을 읽음 처리. 변경 건수 반환 |
| `notify_match_event` | `(match_id: UUID, event: str) -> None` | 매치 시작/종료 시 양쪽 에이전트 팔로워들에게 알림 생성. 팔로워 없으면 조기 반환 |
| `notify_prediction_result` | `(match_id: UUID) -> None` | 매치 결과 확정 시 예측투표 참가자 전원에게 결과 알림 |
| `notify_new_follower` | `(follower_id: UUID, target_type: str, target_id: UUID) -> None` | 신규 팔로우 발생 시 대상(user) 또는 에이전트 소유자(agent.owner_id)에게 알림 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `UserNotification` | `app.models.user_notification` | 알림 ORM 모델 |
| `DebateMatch` | `app.models.debate_match` | 매치 조회 (이벤트·예측 알림) |
| `DebateMatchPrediction` | `app.models.debate_match` | 예측투표 참가자 조회 |
| `DebateAgent` | `app.models.debate_agent` | 에이전트 이름·소유자 조회 |
| `User` | `app.models.user` | 팔로워 닉네임 조회 |
| `FollowService` | `app.services.follow_service` | 에이전트 팔로워 목록 조회 (지연 임포트) |

---

## 호출 흐름

### 알림 일괄 생성 흐름 (`create_bulk`)

```
호출자 (notify_match_event / notify_prediction_result / notify_new_follower)
  → NotificationService.create_bulk(notifications: list[dict])
      ├─ notifications 비어있으면 즉시 반환
      ├─ [정상] UserNotification 객체 생성 → add_all → flush
      └─ [예외 발생]
          → session.rollback()  ← PendingRollback 상태 복구
          → logger.exception()  ← 오류 기록
          (예외 전파하지 않음 — graceful degradation)
```

### 매치 이벤트 알림 흐름 (`notify_match_event`)

```
debate_engine.py 또는 match_service.py
  → async_session() 별도 세션 생성  ← 메인 트랜잭션과 격리
  → NotificationService(session).notify_match_event(match_id, event)
      → DebateMatch 조회 (미존재 시 warning 로그 후 반환)
      → DebateAgent 두 건 배치 조회 (agents_map)
      → from app.services.follow_service import FollowService  ← 지연 임포트
      → FollowService.get_follower_user_ids("agent", agent_a_id)
      → FollowService.get_follower_user_ids("agent", agent_b_id)
      → set 합집합으로 중복 수신자 제거
      ├─ recipient_ids 비어있으면 조기 반환
      └─ event='match_started' / 'match_finished' 분기 → 알림 텍스트 구성
      → create_bulk(notifications)
```

### 예측투표 결과 알림 흐름 (`notify_prediction_result`)

```
debate_engine.py (매치 완료 후)
  → async_session() 별도 세션 생성
  → NotificationService(session).notify_prediction_result(match_id)
      → DebateMatch 조회
      → DebateMatchPrediction 목록 조회 (비어있으면 반환)
      → DebateAgent 두 건 배치 조회
      → winner_id 기준 result_body 구성 (무승부 / A승리 / B승리)
      → 투표자 전원에게 create_bulk
```

### 신규 팔로워 알림 흐름 (`notify_new_follower`)

```
API 라우터 (팔로우 생성 완료 후)
  → NotificationService.notify_new_follower(follower_id, target_type, target_id)
      → User(follower_id) 조회 → nickname 추출
      ├─ [target_type='user']
      │   → recipient_id = target_id
      │   → body = "{nickname}님이 회원님을 팔로우합니다."
      │   → link = None
      └─ [target_type='agent']
          → DebateAgent 조회 (미존재 시 warning 후 반환)
          → recipient_id = agent.owner_id
          → body = "{nickname}님이 에이전트 '{name}'을 팔로우합니다."
          → link = "/debate/agents/{target_id}"
      → create_bulk([단건 알림])
```

---

## 에러 처리

### graceful degradation 패턴

`create_bulk`는 모든 예외를 내부에서 처리하므로 호출자에게 예외가 전파되지 않는다. DB flush 실패 시 세션을 `rollback()`으로 복구하여 `PendingRollbackError` 없이 이후 작업이 계속된다. 알림 누락은 로그로만 기록되며, 토론 진행·매치 결과 저장 등 핵심 흐름에 영향을 주지 않는다.

### 별도 세션 패턴

`engine.py`, `match_service.py`에서 알림 호출 시 `async_session()` 컨텍스트 매니저로 별도 세션을 열어 `NotificationService`를 인스턴스화한다. 이로써 알림 트랜잭션이 메인 트랜잭션과 격리되어, 알림 rollback이 매치 결과 커밋에 영향을 주지 않는다.

### 지연 임포트 패턴

`notify_match_event` 내부에서 `from app.services.follow_service import FollowService`를 함수 진입 시점에 임포트한다. 모듈 최상위에서 임포트하면 `follow_service` ↔ `notification_service` 간 순환 참조가 발생하므로, 지연 임포트로 회피한다.

### 단건 읽음 처리 예외

| 상황 | 예외 | HTTP 변환 |
|---|---|---|
| 알림 미존재 | `ValueError("notification_not_found")` | 404 |
| 소유권 불일치 | `PermissionError("not_owner")` | 403 |

예외 → HTTP 상태코드 변환은 API 라우터가 담당한다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | `notify_new_follower` 호출 흐름에 `link` 값 반영 — `user` 타입은 `None`, `agent` 타입은 `/debate/agents/{id}` |
| 2026-03-12 | 신규 작성 — 팔로우/알림 시스템 도입 |
