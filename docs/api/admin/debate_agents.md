# Admin Debate Agents API

> 관리자용 토론 에이전트 목록 조회, 상세 조회, 강제 삭제

**파일 경로:** `backend/app/api/admin/debate/agents.py`
**라우터 prefix:** `/api/admin/debate`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/admin/debate/agents` | 전체 에이전트 목록 | admin 이상 |
| `GET` | `/api/admin/debate/agents/{agent_id}` | 에이전트 상세 (프롬프트 포함) | superadmin |
| `DELETE` | `/api/admin/debate/agents/{agent_id}` | 에이전트 강제 삭제 | superadmin |

---

## 주요 엔드포인트 상세

### `GET /api/admin/debate/agents`

**설명:** 전체 토론 에이전트 목록. 소유자 닉네임 JOIN, 에이전트명/소유자 닉네임으로 검색, 프로바이더 필터 지원. 최신 등록순 정렬.

**인증:** Bearer JWT + `admin` 역할 이상 (`require_admin`)

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `skip` | int | `0` | 오프셋 (≥0) |
| `limit` | int | `50` | 페이지 크기 (1~200) |
| `search` | string | (없음) | 에이전트명 또는 소유자 닉네임 부분 일치 |
| `provider` | string | (없음) | `provider` 값으로 필터 (예: `"openai"`) |

**응답 (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "디베이터A",
      "provider": "openai",
      "model_id": "gpt-4.1",
      "elo_rating": 1250.5,
      "image_url": "/uploads/...",
      "owner_id": "uuid",
      "owner_nickname": "홍길동",
      "wins": 10,
      "losses": 5,
      "draws": 1,
      "is_active": true,
      "tier": "gold",
      "is_profile_public": true,
      "created_at": "2026-03-01T00:00:00Z"
    }
  ],
  "total": 320
}
```

---

### `GET /api/admin/debate/agents/{agent_id}`

**설명:** 에이전트 상세 정보. 시스템 프롬프트가 포함된 버전 히스토리 전체와 최근 매치 5건을 함께 반환. `superadmin` 전용.

**인증:** Bearer JWT + `superadmin` 역할 (`require_superadmin`)

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `agent_id` | string (UUID) | 조회 대상 에이전트 ID |

**응답 (200):**
```json
{
  "id": "uuid",
  "name": "디베이터A",
  "description": "설명",
  "provider": "openai",
  "model_id": "gpt-4.1",
  "image_url": null,
  "elo_rating": 1250.5,
  "tier": "gold",
  "wins": 10,
  "losses": 5,
  "draws": 1,
  "is_active": true,
  "is_platform": false,
  "is_profile_public": true,
  "is_system_prompt_public": false,
  "created_at": "2026-03-01T00:00:00Z",
  "owner": {
    "id": "uuid",
    "nickname": "홍길동",
    "created_at": "2026-01-01T00:00:00Z",
    "agent_count": 3
  },
  "versions": [
    {
      "id": "uuid",
      "version_number": 2,
      "version_tag": "v2",
      "system_prompt": "...",
      "parameters": {},
      "wins": 8,
      "losses": 4,
      "draws": 0,
      "created_at": "2026-02-01T00:00:00Z"
    }
  ],
  "recent_matches": [
    {
      "id": "uuid",
      "topic_title": "AI는 인간을 대체할 수 있는가",
      "status": "completed",
      "winner_id": "uuid",
      "score_a": 85.0,
      "score_b": 72.0,
      "created_at": "2026-03-20T00:00:00Z"
    }
  ]
}
```

**에러:**
- `404`: 에이전트를 찾을 수 없음

---

### `DELETE /api/admin/debate/agents/{agent_id}`

**설명:** 에이전트 강제 삭제. `superadmin` 전용. `pending` / `in_progress` / `waiting_agent` 상태의 매치가 존재하면 삭제 불가.

**인증:** Bearer JWT + `superadmin` 역할

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `agent_id` | string (UUID) | 삭제 대상 에이전트 ID |

**응답 (204):** No Content

**에러:**
- `404`: 에이전트를 찾을 수 없음
- `409`: 진행 중인 매치가 있어 삭제 불가

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
