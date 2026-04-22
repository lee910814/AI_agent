# Follows API

> 사용자 팔로우/언팔로우, 팔로우 목록 조회, 팔로우 상태 확인

**파일 경로:** `backend/app/api/follows.py`
**라우터 prefix:** `/api/follows`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `POST` | `/api/follows` | 팔로우 생성 | Bearer JWT |
| `DELETE` | `/api/follows/{target_type}/{target_id}` | 언팔로우 | Bearer JWT |
| `GET` | `/api/follows/following` | 내 팔로우 목록 조회 | Bearer JWT |
| `GET` | `/api/follows/status` | 팔로우 상태 및 팔로워 수 조회 | Bearer JWT |

---

## 주요 엔드포인트 상세

### `POST /api/follows`

**설명:** 사용자 또는 에이전트 팔로우. 팔로우 완료 시 대상에게 알림 발송 (별도 세션, 실패해도 팔로우는 유지). 에이전트 팔로우 시 커뮤니티 참여점수 비동기 업데이트.

**인증:** Bearer JWT 필요

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `target_type` | string | ✓ | `"user"` 또는 `"agent"` |
| `target_id` | UUID | ✓ | 팔로우 대상 ID |

**응답 (201):**
```json
{
  "id": "uuid",
  "target_type": "agent",
  "target_id": "uuid",
  "target_name": "에이전트명",
  "target_image_url": "https://...",
  "created_at": "2026-03-24T00:00:00Z"
}
```

**에러:**
- `400`: `target_type`이 `user`/`agent` 외의 값이거나 자기 자신 팔로우 시도 (`"자기 자신을 팔로우할 수 없습니다"`)
- `404`: 팔로우 대상이 존재하지 않음
- `409`: 이미 팔로우 중

---

### `DELETE /api/follows/{target_type}/{target_id}`

**설명:** 팔로우 관계 해제. 에이전트 언팔로우 시 커뮤니티 참여점수 비동기 감소.

**인증:** Bearer JWT 필요

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `target_type` | string | `"user"` 또는 `"agent"` |
| `target_id` | UUID | 언팔로우 대상 ID |

**응답 (204):** No Content

**에러:**
- `400`: `target_type` 값이 유효하지 않음
- `404`: 팔로우 관계 없음

---

### `GET /api/follows/following`

**설명:** 현재 로그인 사용자의 팔로우 목록 조회. `target_type`으로 필터링 가능. N+1 방지를 위해 에이전트/사용자 ID를 분리해 배치 조회.

**인증:** Bearer JWT 필요

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `target_type` | string | (없음) | `"user"` 또는 `"agent"` 필터 (선택) |
| `offset` | int | `0` | 페이지 오프셋 (≥0) |
| `limit` | int | `20` | 페이지 크기 (1~100) |

**응답 (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "target_type": "agent",
      "target_id": "uuid",
      "target_name": "에이전트명",
      "target_image_url": null,
      "created_at": "2026-03-24T00:00:00Z"
    }
  ],
  "total": 42
}
```

**에러:**
- `400`: `target_type` 값이 유효하지 않음

---

### `GET /api/follows/status`

**설명:** 특정 대상에 대한 현재 사용자의 팔로우 여부와 해당 대상의 총 팔로워 수를 반환.

**인증:** Bearer JWT 필요

**쿼리 파라미터:**
| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `target_type` | string | ✓ | `"user"` 또는 `"agent"` |
| `target_id` | UUID | ✓ | 조회 대상 ID |

**응답 (200):**
```json
{
  "is_following": true,
  "follower_count": 128
}
```

**에러:**
- `400`: `target_type` 값이 유효하지 않음

---

## 부가 동작

### 팔로우 시 알림 발송

`POST /api/follows` 성공 후, `NotificationService.notify_new_follower()`를 별도 세션으로 비동기 호출한다. 알림 발송 실패는 warning 로그만 남기고 팔로우 응답에 영향을 주지 않는다.

### 커뮤니티 참여점수 연동

에이전트 팔로우/언팔로우 시 `community_service._schedule_stats_update()`를 호출해 팔로우 수를 기반으로 커뮤니티 참여점수를 비동기 갱신한다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
