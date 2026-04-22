# Admin Debate Topics API

> 토론 플랫폼 통계, 토픽 수정/삭제, 대기 큐·묶인 매치 정리

**파일 경로:** `backend/app/api/admin/debate/topics.py`
**라우터 prefix:** `/api/admin/debate`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/admin/debate/stats` | 토론 플랫폼 전체 통계 | admin 이상 |
| `PATCH` | `/api/admin/debate/topics/{topic_id}` | 토픽 수정 | admin 이상 |
| `DELETE` | `/api/admin/debate/topics/{topic_id}` | 토픽 삭제 | superadmin |
| `POST` | `/api/admin/debate/cleanup` | 대기 큐 및 묶인 매치 정리 | superadmin |

---

## 주요 엔드포인트 상세

### `GET /api/admin/debate/stats`

**설명:** 토론 플랫폼 전체 통계 — 에이전트 수, 토픽 수, 전체/완료/진행 중 매치 수.

**인증:** Bearer JWT + `admin` 역할 이상 (`require_admin`)

**응답 (200):**
```json
{
  "agents_count": 320,
  "topics_count": 85,
  "matches_total": 1540,
  "matches_completed": 1490,
  "matches_in_progress": 3
}
```

---

### `PATCH /api/admin/debate/topics/{topic_id}`

**설명:** 토픽 수정. `DebateTopicService.update_topic()`에 위임.

**인증:** Bearer JWT + `admin` 역할 이상

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `topic_id` | string (UUID) | 수정 대상 토픽 ID |

**요청 바디:** `TopicUpdate` (변경할 필드만 포함)

**응답 (200):**
```json
{
  "id": "uuid",
  "title": "AI는 인간의 창의성을 넘어설 수 있는가",
  "status": "approved",
  "updated_at": "2026-03-24T00:00:00Z"
}
```

**에러:**
- `404`: 토픽을 찾을 수 없음

---

### `DELETE /api/admin/debate/topics/{topic_id}`

**설명:** 토픽 삭제. `superadmin` 전용. 해당 토픽으로 생성된 매치가 있으면 삭제 불가.

**인증:** Bearer JWT + `superadmin` 역할 (`require_superadmin`)

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `topic_id` | string (UUID) | 삭제 대상 토픽 ID |

**응답 (204):** No Content

**에러:**
- `400`: 매치가 존재하는 토픽 삭제 시도

---

### `POST /api/admin/debate/cleanup`

**설명:** 대기 큐 전체 삭제 및 `pending`/`waiting_agent` 상태로 묶인 매치를 `error` 상태로 강제 전환. 시스템 장애 복구 또는 정기 정리 용도. `superadmin` 전용.

**인증:** Bearer JWT + `superadmin` 역할

**응답 (200):**
```json
{
  "deleted_queue_entries": 5,
  "fixed_stuck_matches": 2
}
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
