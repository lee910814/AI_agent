# Admin Debate Templates API

> 관리자 제공 에이전트 템플릿 관리 — 목록 조회, 상세 조회, 생성, 수정

**파일 경로:** `backend/app/api/admin/debate/templates.py`
**라우터 prefix:** `/api/admin/debate`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/admin/debate/templates` | 전체 템플릿 목록 (비활성 포함) | admin 이상 |
| `GET` | `/api/admin/debate/templates/{template_id}` | 템플릿 상세 조회 | admin 이상 |
| `POST` | `/api/admin/debate/templates` | 템플릿 생성 | superadmin |
| `PATCH` | `/api/admin/debate/templates/{template_id}` | 템플릿 수정 | superadmin |

---

## 주요 엔드포인트 상세

### `GET /api/admin/debate/templates`

**설명:** 비활성 포함 전체 에이전트 템플릿 목록 반환. 사용자 대상 조회와 달리 비활성 템플릿도 포함.

**인증:** Bearer JWT + `admin` 역할 이상 (`require_admin`)

**응답 (200):** `AgentTemplateAdminResponse[]`

---

### `GET /api/admin/debate/templates/{template_id}`

**설명:** 특정 템플릿 상세 조회.

**인증:** Bearer JWT + `admin` 역할 이상

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `template_id` | string (UUID) | 조회 대상 템플릿 ID |

**응답 (200):** `AgentTemplateAdminResponse`

**에러:**
- `404`: 템플릿을 찾을 수 없음

---

### `POST /api/admin/debate/templates`

**설명:** 새 에이전트 템플릿 생성. `superadmin` 전용. 사용자가 에이전트 생성 시 템플릿으로 선택 가능.

**인증:** Bearer JWT + `superadmin` 역할 (`require_superadmin`)

**요청 바디:** `AgentTemplateCreate`

**응답 (201):** 생성된 `AgentTemplateAdminResponse`

**에러:**
- `422`: 유효하지 않은 데이터

---

### `PATCH /api/admin/debate/templates/{template_id}`

**설명:** 기존 템플릿 수정. `superadmin` 전용. 부분 업데이트 지원.

**인증:** Bearer JWT + `superadmin` 역할

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `template_id` | string (UUID) | 수정 대상 템플릿 ID |

**요청 바디:** `AgentTemplateUpdate` (변경할 필드만 포함)

**응답 (200):** 변경된 `AgentTemplateAdminResponse`

**에러:**
- `404`: 템플릿을 찾을 수 없음

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
