# FollowService

> 사용자 → 사용자/에이전트 팔로우 관계를 생성·삭제·조회하는 서비스 계층

**파일 경로:** `backend/app/services/follow_service.py`
**최종 수정일:** 2026-03-12

---

## 모듈 목적

`FollowService`는 사용자가 다른 사용자 또는 에이전트를 팔로우하는 기능을 담당한다.

- `target_type='user'` — `users` 테이블에서 대상 존재 여부를 검증한 뒤 팔로우 생성
- `target_type='agent'` — `debate_agents` 테이블에서 대상 존재 여부를 검증한 뒤 팔로우 생성
- 팔로워 user_id 목록 조회(`get_follower_user_ids`)는 `NotificationService.notify_match_event()`에서 알림 수신자 결정에 사용된다.

---

## 주요 상수

없음

---

## 클래스: FollowService

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
| `follow` | `(follower_id: UUID, target_type: str, target_id: UUID) -> UserFollow` | 팔로우 생성. target_type에 따라 대상 존재 확인. 자기 자신 팔로우 및 중복 팔로우 방지 |
| `unfollow` | `(follower_id: UUID, target_type: str, target_id: UUID) -> None` | 팔로우 삭제. 팔로우 레코드 미존재 시 `ValueError("not_following")` |
| `get_following` | `(user_id: UUID, target_type: str \| None, offset: int, limit: int) -> tuple[list[UserFollow], int]` | 내 팔로우 목록 + 전체 수 반환. `target_type` 파라미터로 user/agent 필터 선택적 적용. `created_at DESC` 정렬 |
| `get_follower_count` | `(target_type: str, target_id: UUID) -> int` | 특정 대상의 팔로워 수 반환 |
| `is_following` | `(follower_id: UUID, target_type: str, target_id: UUID) -> bool` | 팔로우 여부 확인 |
| `get_follower_user_ids` | `(target_type: str, target_id: UUID) -> list[UUID]` | 특정 대상의 팔로워 user_id 목록 반환. 알림 발송 수신자 결정에 사용 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `UserFollow` | `app.models.user_follow` | 팔로우 관계 ORM 모델 |
| `DebateAgent` | `app.models.debate_agent` | `target_type='agent'` 대상 존재 검증 |
| `User` | `app.models.user` | `target_type='user'` 대상 존재 검증 |

---

## 호출 흐름

### 팔로우 생성 흐름

```
API 라우터
  → FollowService.follow(follower_id, target_type, target_id)
      ├─ [target_type='user']
      │   ├─ follower_id == target_id → ValueError("self_follow")
      │   └─ users 테이블 존재 확인 → 미존재 시 ValueError("target_not_found")
      ├─ [target_type='agent']
      │   └─ debate_agents 테이블 존재 확인 → 미존재 시 ValueError("target_not_found")
      └─ [그 외] → ValueError("invalid_target_type")
      → UserFollow INSERT (flush)
      → IntegrityError 발생 시 rollback → ValueError("already_following")
```

### 알림 연동 흐름

```
NotificationService.notify_match_event(match_id, event)
  → FollowService(self.db) 인스턴스 생성 (지연 임포트 없이 동일 세션 공유)
  → get_follower_user_ids("agent", agent_a_id)
  → get_follower_user_ids("agent", agent_b_id)
  → set 합집합으로 중복 수신자 제거
  → NotificationService.create_bulk(notifications)
```

### 팔로우 목록 조회 흐름

```
API 라우터
  → FollowService.get_following(user_id, target_type, offset, limit)
      ├─ target_type 있음 → WHERE follower_id = ? AND target_type = ?
      └─ target_type 없음 → WHERE follower_id = ?
      → COUNT 쿼리 + SELECT 쿼리 순차 실행
      → (items, total) 반환
```

---

## 에러 처리

| 상황 | 예외 | HTTP 변환 |
|---|---|---|
| 자기 자신 팔로우 (`target_type='user'`, `target_id == follower_id`) | `ValueError("self_follow")` | 400 |
| 대상 미존재 | `ValueError("target_not_found")` | 404 |
| 유효하지 않은 target_type | `ValueError("invalid_target_type")` | 400 |
| 이미 팔로우 중 (UniqueConstraint 위반) | `ValueError("already_following")` | 409 |
| 팔로우 레코드 미존재 시 언팔로우 | `ValueError("not_following")` | 404 |

예외 → HTTP 상태코드 변환은 API 라우터가 담당한다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-12 | 신규 작성 — 팔로우 시스템 도입 |
