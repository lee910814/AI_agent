# Auth API

> 회원가입, 로그인, 로그아웃, 프로필 수정 등 사용자 인증 관련 엔드포인트

**파일 경로:** `backend/app/api/auth.py`
**라우터 prefix:** `/api/auth`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| GET | `/api/auth/check-nickname` | 닉네임 사용 가능 여부 확인 | public |
| GET | `/api/auth/check-login-id` | 로그인 ID 사용 가능 여부 확인 | public |
| POST | `/api/auth/register` | 회원가입 및 JWT 발급 | public |
| POST | `/api/auth/login` | 로그인 및 JWT 발급 | public |
| POST | `/api/auth/logout` | 로그아웃 (토큰 무효화) | user (선택) |
| GET | `/api/auth/me` | 현재 사용자 정보 조회 | user |
| PUT | `/api/auth/me` | 프로필 정보 수정 | user |
| PUT | `/api/auth/me/password` | 비밀번호 변경 | user |

---

## 인증 방식

두 가지 방식을 모두 지원하며 우선순위는 `Authorization` 헤더 > `access_token` 쿠키 순이다.

- **Bearer Token**: `Authorization: Bearer <JWT>`
- **HttpOnly 쿠키**: 로그인/회원가입 성공 시 서버가 `access_token` 쿠키를 자동 설정함 (`SameSite=lax`, 프로덕션에서 `Secure=true`)

단일 세션 정책이 적용된다. 새 기기에서 로그인하면 이전 기기의 토큰은 다음 요청 시 자동으로 거부된다.

---

## 주요 엔드포인트 상세

### `GET /api/auth/check-nickname` — 닉네임 중복 확인

**파라미터 (Query):**
| 이름 | 타입 | 필수 | 설명 |
|---|---|---|---|
| nickname | string | O | 중복 체크할 닉네임 |

**응답 (200):**
```json
{ "available": true }
```

---

### `GET /api/auth/check-login-id` — 로그인 ID 중복 확인

**파라미터 (Query):**
| 이름 | 타입 | 필수 | 설명 |
|---|---|---|---|
| login_id | string | O | 중복 체크할 로그인 ID |

**응답 (200):**
```json
{ "available": false }
```

---

### `POST /api/auth/register` — 회원가입

JWT를 발급하고 `access_token` HttpOnly 쿠키를 응답에 설정한다.

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| login_id | string | O | 영문·숫자·밑줄, 2~30자 |
| nickname | string | O | 한글·영문·숫자·밑줄, 2~20자 |
| password | string | O | 영문+숫자 포함, 8~100자 |
| email | string | - | 이메일 주소 (선택) |

**응답 (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**에러:**
| 코드 | 조건 |
|---|---|
| 400 | `login_id` 또는 `nickname`에 'admin' 문자열 포함 |
| 409 | 닉네임 중복 |
| 422 | 입력값 유효성 검사 실패 |

---

### `POST /api/auth/login` — 로그인

성공 시 이전 세션은 자동으로 무효화된다 (단일 세션 정책). JWT 발급 및 `access_token` 쿠키를 설정한다.

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| login_id | string | O | 로그인 아이디 |
| password | string | O | 비밀번호 |

**응답 (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**에러:**
| 코드 | 조건 |
|---|---|
| 401 | 아이디/비밀번호 불일치 |

---

### `POST /api/auth/logout` — 로그아웃

현재 토큰을 Redis 블랙리스트에 추가하고 세션을 삭제한다. `access_token` 쿠키를 삭제한다. 토큰이 없어도 200을 반환한다.

**응답 (200):**
```json
{ "message": "Logged out successfully" }
```

---

### `GET /api/auth/me` — 현재 사용자 정보 조회

**인증:** Bearer JWT 또는 HttpOnly 쿠키 필수

**응답 (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "login_id": "user123",
  "nickname": "홍길동",
  "role": "user",
  "age_group": "adult",
  "adult_verified_at": null,
  "preferred_llm_model_id": null,
  "preferred_themes": null,
  "created_at": "2026-01-01T00:00:00Z"
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| role | string | `user` / `admin` / `superadmin` |
| age_group | string | `minor_safe` / `adult` |

---

### `PUT /api/auth/me` — 프로필 수정

**인증:** Bearer JWT 필수

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| nickname | string | - | 변경할 닉네임 |
| preferred_themes | array\<string\> | - | 선호 테마 목록 |

**에러:**
| 코드 | 조건 |
|---|---|
| 400 | 일반 사용자가 'admin' 포함 닉네임으로 변경 시도 |
| 409 | 닉네임 중복 |

---

### `PUT /api/auth/me/password` — 비밀번호 변경

성공 시 기존 토큰을 블랙리스트 처리하고 새 JWT를 발급한다.

**인증:** Bearer JWT 필수

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| current_password | string | O | 현재 비밀번호 |
| new_password | string | O | 새 비밀번호 (영문+숫자 포함, 8~100자) |

**응답 (200):**
```json
{
  "message": "Password changed successfully",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**에러:**
| 코드 | 조건 |
|---|---|
| 400 | 현재 비밀번호 불일치 |

---

## 의존 서비스

| 서비스 | 역할 |
|---|---|
| `UserService` | 사용자 생성, 인증, 프로필 수정, 비밀번호 변경 |
| `core/auth.py` | JWT 발급/검증, 블랙리스트, Redis 세션 관리 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
