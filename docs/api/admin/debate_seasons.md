# Admin Debate Seasons API

> 시즌 생성, 목록 조회, 활성화, 종료, 삭제

**파일 경로:** `backend/app/api/admin/debate/seasons.py`
**라우터 prefix:** `/api/admin/debate`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `POST` | `/api/admin/debate/seasons` | 시즌 생성 | superadmin |
| `GET` | `/api/admin/debate/seasons` | 전체 시즌 목록 | superadmin |
| `POST` | `/api/admin/debate/seasons/{season_id}/activate` | 시즌 활성화 | superadmin |
| `POST` | `/api/admin/debate/seasons/{season_id}/close` | 시즌 종료 | superadmin |
| `DELETE` | `/api/admin/debate/seasons/{season_id}` | 시즌 삭제 | superadmin |

모든 엔드포인트는 `superadmin` 역할(`require_superadmin`)이 필요합니다.

---

## 시즌 상태 전이

```
upcoming → (activate) → active → (close) → closed
```

- `upcoming` 상태만 활성화 및 삭제 가능
- 동시에 `active` 상태 시즌은 1개만 존재 가능
- 시즌 종료 시 `DebateSeasonService.close_season()`이 최종 순위 스냅샷 저장

---

## 주요 엔드포인트 상세

### `POST /api/admin/debate/seasons`

**설명:** 새 시즌 생성. 초기 상태는 `upcoming`.

**요청 바디:** `SeasonCreate`
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `season_number` | int | ✓ | 시즌 번호 |
| `title` | string | ✓ | 시즌 제목 |
| `start_at` | datetime | ✓ | 시작 일시 (ISO 8601) |
| `end_at` | datetime | ✓ | 종료 예정 일시 (ISO 8601) |

**응답 (201):**
```json
{
  "id": "uuid",
  "status": "upcoming"
}
```

---

### `GET /api/admin/debate/seasons`

**설명:** 전체 시즌 목록을 시즌 번호 내림차순으로 반환.

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `skip` | int | `0` | 오프셋 (≥0) |
| `limit` | int | `20` | 페이지 크기 (1~100) |

**응답 (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "season_number": 3,
      "title": "시즌 3",
      "start_at": "2026-04-01T00:00:00Z",
      "end_at": "2026-06-30T23:59:59Z",
      "status": "upcoming"
    }
  ],
  "total": 3
}
```

---

### `POST /api/admin/debate/seasons/{season_id}/activate`

**설명:** `upcoming` 상태 시즌을 `active`로 전환. 이미 `active` 시즌이 있으면 먼저 종료 필요.

**에러:**
- `400`: 이미 활성 시즌이 존재하거나 대상 시즌이 `upcoming` 상태가 아님
- `404`: 시즌을 찾을 수 없음

**응답 (200):**
```json
{ "ok": true }
```

---

### `POST /api/admin/debate/seasons/{season_id}/close`

**설명:** 시즌 종료. `DebateSeasonService.close_season()`을 통해 최종 순위 스냅샷(`debate_season_results`)을 저장.

**에러:**
- `400`: 종료할 수 없는 상태 (서비스 레이어 `ValueError`)
- `404`: 시즌을 찾을 수 없음

**응답 (200):**
```json
{ "ok": true }
```

---

### `DELETE /api/admin/debate/seasons/{season_id}`

**설명:** 시즌 삭제. `upcoming` 상태만 삭제 가능.

**에러:**
- `400`: `upcoming` 상태가 아닌 시즌
- `404`: 시즌을 찾을 수 없음

**응답 (204):** No Content

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
