# Admin Users API

> 사용자 목록 조회, 상세 조회, 역할 변경, 일괄 삭제

**파일 경로:** `backend/app/api/admin/system/users.py`
**라우터 prefix:** `/api/admin/users`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/admin/users` | 사용자 목록 (검색/필터/정렬) | admin 이상 |
| `GET` | `/api/admin/users/{user_id}` | 사용자 상세 정보 | admin 이상 |
| `PUT` | `/api/admin/users/{user_id}/role` | 사용자 역할 변경 | superadmin |
| `POST` | `/api/admin/users/bulk-delete` | 사용자 일괄 삭제 | superadmin |

---

## 주요 엔드포인트 상세

### `GET /api/admin/users`

**설명:** 전체 사용자 목록을 서버사이드 검색·필터·정렬과 함께 반환. 응답에 역할별/연령대별 통계(`stats`)가 포함됨.

**인증:** Bearer JWT + `admin` 역할 이상 (`require_admin`)

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `skip` | int | `0` | 오프셋 (≥0) |
| `limit` | int | `20` | 페이지 크기 (1~100) |
| `search` | string | (없음) | 닉네임/로그인ID 부분 일치 검색 (최대 50자) |
| `role` | string | (없음) | `"user"` / `"admin"` / `"superadmin"` 필터 |
| `age_group` | string | (없음) | `age_group` 컬럼 값으로 필터 |
| `sort_by` | string | `"created_at"` | 정렬 기준: `created_at` / `credit_balance` / `nickname` |
| `has_agents` | bool | (없음) | `true`: 에이전트 보유 사용자만, `false`: 미보유 사용자만 |

**응답 (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "login_id": "user01",
      "nickname": "홍길동",
      "role": "user",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "total": 150,
  "stats": {
    "total_users": 150,
    "superadmin_count": 1,
    "admin_count": 3,
    "adult_verified_count": 45,
    "unverified_count": 100,
    "minor_safe_count": 5
  }
}
```

---

### `GET /api/admin/users/{user_id}`

**설명:** 특정 사용자의 상세 정보. 크레딧 잔액, 성인인증 일시, 선호 모델, 역할 등 포함.

**인증:** Bearer JWT + `admin` 역할 이상

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `user_id` | UUID | 조회 대상 사용자 ID |

**응답 (200):** `AdminUserDetailResponse`
```json
{
  "id": "uuid",
  "login_id": "user01",
  "nickname": "홍길동",
  "role": "user",
  "age_group": "unverified",
  "adult_verified_at": null,
  "preferred_llm_model_id": "uuid",
  "preferred_themes": [],
  "credit_balance": 5000,
  "last_credit_grant_at": null,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-03-20T00:00:00Z",
  "session_count": 0,
  "message_count": 0,
  "subscription_status": null
}
```

**에러:**
- `404`: 사용자를 찾을 수 없음

---

### `PUT /api/admin/users/{user_id}/role`

**설명:** 사용자의 역할을 변경. `superadmin` 전용.

**인증:** Bearer JWT + `superadmin` 역할 (`require_superadmin`)

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `user_id` | UUID | 대상 사용자 ID |

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `role` | string | ✓ | `"user"` / `"admin"` / `"superadmin"` |

**응답 (200):** 변경된 `UserResponse`

**에러:**
- `404`: 사용자를 찾을 수 없음
- `422`: `role` 값이 유효하지 않음

---

### `POST /api/admin/users/bulk-delete`

**설명:** 사용자 일괄 삭제. `superadmin` 전용. 관리자 계정(`admin`/`superadmin` 역할) 및 요청자 본인은 삭제 대상에서 자동 제외되며 `skipped_admin_ids`에 포함.

**인증:** Bearer JWT + `superadmin` 역할

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `user_ids` | UUID[] | ✓ | 삭제할 사용자 ID 목록 |

**응답 (200):** `BulkDeleteResponse`
```json
{
  "deleted_count": 5,
  "skipped_admin_ids": ["uuid1", "uuid2"]
}
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
