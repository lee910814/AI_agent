# Admin Debate Tournaments API

> 관리자용 토너먼트 생성 및 시작

**파일 경로:** `backend/app/api/admin/debate/tournaments.py`
**라우터 prefix:** `/api/admin/debate`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `POST` | `/api/admin/debate/tournaments` | 토너먼트 생성 | superadmin |
| `POST` | `/api/admin/debate/tournaments/{tournament_id}/start` | 토너먼트 시작 | superadmin |

모든 엔드포인트는 `superadmin` 역할(`require_superadmin`)이 필요합니다.

---

## 토너먼트 상태 전이

```
registration → (start) → in_progress → completed
```

- 생성 직후 상태: `registration` (참가 신청 가능)
- `start` 호출 후: `in_progress` (`current_round = 1`, `started_at` 기록)
- 이미 `in_progress` 이상인 토너먼트는 재시작 불가

---

## 주요 엔드포인트 상세

### `POST /api/admin/debate/tournaments`

**설명:** 새 토너먼트 생성. `DebateTournamentService.create_tournament()`가 대진표 구조 초기화. `superadmin` 전용.

**인증:** Bearer JWT + `superadmin` 역할 (`require_superadmin`)

**요청 바디:** `TournamentCreate`
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `title` | string | ✓ | 토너먼트 제목 |
| `topic_id` | UUID | ✓ | 사용할 토픽 ID |
| `bracket_size` | int | ✓ | 대진표 크기 (보통 8 또는 16의 2의 거듭제곱) |

**응답 (201):**
```json
{
  "id": "uuid"
}
```

---

### `POST /api/admin/debate/tournaments/{tournament_id}/start`

**설명:** 토너먼트를 `registration` 상태에서 `in_progress`로 전환. `current_round`를 1로 설정하고 `started_at` 기록. `superadmin` 전용.

**인증:** Bearer JWT + `superadmin` 역할

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `tournament_id` | string (UUID) | 시작할 토너먼트 ID |

**응답 (200):**
```json
{ "ok": true }
```

**에러:**
- `400`: `registration` 상태가 아닌 토너먼트 (이미 시작됨)
- `404`: 토너먼트를 찾을 수 없음

---

## 관련 문서

사용자 대상 토너먼트 조회/참가 API는 `GET /api/tournaments/*` 참조.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
