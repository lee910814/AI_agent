# Admin Usage API

> 전체 사용량 통계, 사용자별 사용량 조회, 토큰 쿼터 관리

**파일 경로:** `backend/app/api/admin/system/usage.py`
**라우터 prefix:** `/api/admin/usage`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/admin/usage/summary` | 전체 사용량 통계 | admin 이상 |
| `GET` | `/api/admin/usage/users/{user_id}` | 특정 사용자 상세 사용량 | admin 이상 |
| `GET` | `/api/admin/usage/user-search` | 닉네임/로그인ID로 사용자 검색 | admin 이상 |
| `GET` | `/api/admin/usage/quotas` | 커스텀 쿼터 설정 사용자 목록 | admin 이상 |
| `GET` | `/api/admin/usage/quotas/{user_id}` | 특정 사용자 쿼터 조회 | admin 이상 |
| `PUT` | `/api/admin/usage/quotas/{user_id}` | 특정 사용자 쿼터 설정 (upsert) | admin 이상 |

---

## 주요 엔드포인트 상세

### `GET /api/admin/usage/summary`

**설명:** 플랫폼 전체 토큰 사용량 및 비용 통계. `UsageService.get_admin_summary()` 위임.

**인증:** Bearer JWT + `admin` 역할 이상 (`require_admin`)

**응답 (200):** `UsageService.get_admin_summary()` 반환값 (서비스 내부 집계)

---

### `GET /api/admin/usage/users/{user_id}`

**설명:** 특정 사용자의 상세 사용량 조회. `UsageService.get_user_usage_admin()` 위임.

**인증:** Bearer JWT + `admin` 역할 이상

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `user_id` | UUID | 조회 대상 사용자 ID |

---

### `GET /api/admin/usage/user-search`

**설명:** 닉네임 또는 로그인 ID(부분 일치, 대소문자 무시)로 사용자를 검색. 최대 10건 반환.

**인증:** Bearer JWT + `admin` 역할 이상

**쿼리 파라미터:**
| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `q` | string | ✓ | 검색 키워드 (1~50자) |

**응답 (200):**
```json
[
  {
    "id": "uuid",
    "nickname": "홍길동",
    "login_id": "hong123"
  }
]
```

---

### `GET /api/admin/usage/quotas`

**설명:** `daily_token_limit` 또는 `monthly_token_limit`이 설정된 사용자 목록을 닉네임 오름차순으로 반환.

**인증:** Bearer JWT + `admin` 역할 이상

**응답 (200):**
```json
[
  {
    "user_id": "uuid",
    "nickname": "홍길동",
    "daily_token_limit": 100000,
    "monthly_token_limit": 2000000
  }
]
```

---

### `GET /api/admin/usage/quotas/{user_id}`

**설명:** 특정 사용자의 토큰 쿼터 조회. 쿼터가 설정되지 않은 경우 `null` 반환.

**인증:** Bearer JWT + `admin` 역할 이상

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `user_id` | UUID | 조회 대상 사용자 ID |

**응답 (200):**
```json
{
  "user_id": "uuid",
  "nickname": "홍길동",
  "daily_token_limit": 100000,
  "monthly_token_limit": 2000000
}
```

**에러:**
- `404`: 사용자를 찾을 수 없음

---

### `PUT /api/admin/usage/quotas/{user_id}`

**설명:** 특정 사용자의 일/월 토큰 쿼터를 설정(upsert). `null`로 설정하면 해당 쿼터 해제.

**인증:** Bearer JWT + `admin` 역할 이상

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `user_id` | UUID | 대상 사용자 ID |

**요청 바디:**
| 필드 | 타입 | 설명 |
|---|---|---|
| `daily_token_limit` | int \| null | 일별 토큰 한도 (null이면 해제) |
| `monthly_token_limit` | int \| null | 월별 토큰 한도 (null이면 해제) |

**응답 (200):**
```json
{
  "user_id": "uuid",
  "nickname": "홍길동",
  "daily_token_limit": 100000,
  "monthly_token_limit": 2000000
}
```

**에러:**
- `404`: 사용자를 찾을 수 없음

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
