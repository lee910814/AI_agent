# Notifications API

> 알림 목록 조회, 단건/전체 읽음 처리, 미읽기 수 조회

**파일 경로:** `backend/app/api/notifications.py`
**라우터 prefix:** `/api/notifications`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/notifications` | 알림 목록 조회 | Bearer JWT |
| `GET` | `/api/notifications/unread-count` | 미읽기 알림 수 조회 | Bearer JWT |
| `PUT` | `/api/notifications/read-all` | 전체 알림 읽음 처리 | Bearer JWT |
| `PUT` | `/api/notifications/{notification_id}/read` | 단건 알림 읽음 처리 | Bearer JWT |

---

## 주요 엔드포인트 상세

### `GET /api/notifications`

**설명:** 현재 로그인 사용자의 알림 목록을 페이지네이션으로 반환. `unread_only=true`이면 읽지 않은 알림만 반환.

**인증:** Bearer JWT 필요

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `offset` | int | `0` | 페이지 오프셋 (≥0) |
| `limit` | int | `20` | 페이지 크기 (1~100) |
| `unread_only` | bool | `false` | `true`이면 미읽기 알림만 반환 |

**응답 (200):** `NotificationListResponse`
```json
{
  "items": [
    {
      "id": "uuid",
      "type": "new_follower",
      "is_read": false,
      "payload": {},
      "created_at": "2026-03-24T00:00:00Z"
    }
  ],
  "total": 15,
  "unread_count": 3
}
```

---

### `GET /api/notifications/unread-count`

**설명:** 현재 사용자의 읽지 않은 알림 수만 빠르게 반환. 헤더 배지 업데이트 등 경량 폴링 용도.

**인증:** Bearer JWT 필요

**응답 (200):**
```json
{
  "count": 3
}
```

---

### `PUT /api/notifications/read-all`

**설명:** 현재 사용자의 모든 알림을 읽음 처리.

**인증:** Bearer JWT 필요

**응답 (200):**
```json
{
  "updated": 5
}
```

**비고:** `updated`는 실제로 읽음 처리된 알림 수.

---

### `PUT /api/notifications/{notification_id}/read`

**설명:** 특정 알림 하나를 읽음 처리. 본인 소유 알림만 처리 가능.

**인증:** Bearer JWT 필요

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `notification_id` | UUID | 읽음 처리할 알림 ID |

**응답 (200):**
```json
{
  "ok": true
}
```

**에러:**
- `403`: 본인 소유 알림이 아닌 경우
- `404`: 알림을 찾을 수 없음

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
