# Admin Monitoring API

> 시스템 통계 및 토큰 사용 로그 조회

**파일 경로:** `backend/app/api/admin/system/monitoring.py`
**라우터 prefix:** `/api/admin/monitoring`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/admin/monitoring/stats` | 시스템 통계 (사용자/에이전트/매치 수) | admin 이상 |
| `GET` | `/api/admin/monitoring/logs` | 최근 토큰 사용 로그 | admin 이상 |
| `GET` | `/api/admin/monitoring/logs/{log_id}` | 토큰 사용 로그 단건 상세 | admin 이상 |

---

## 주요 엔드포인트 상세

### `GET /api/admin/monitoring/stats`

**설명:** 전체 사용자·에이전트·매치 수 및 최근 7일 신규 가입자 수를 반환.

**인증:** Bearer JWT + `admin` 역할 이상 (`require_admin`)

**응답 (200):**
```json
{
  "totals": {
    "users": 150,
    "agents": 320,
    "matches": 1540
  },
  "weekly": {
    "new_users": 12
  }
}
```

---

### `GET /api/admin/monitoring/logs`

**설명:** 지정 기간 내 토큰 사용 로그를 최신순으로 반환. 사용자 닉네임과 모델명을 JOIN해서 제공. `total_tokens`는 `input_tokens + output_tokens` 계산값.

**인증:** Bearer JWT + `admin` 역할 이상

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `days` | int | `7` | 조회 기간 (1~90일) |
| `limit` | int | `50` | 최대 반환 건수 (1~200) |

**응답 (200):**
```json
{
  "logs": [
    {
      "id": 1,
      "user_id": "uuid",
      "user_nickname": "홍길동",
      "session_id": "uuid",
      "llm_model_id": "uuid",
      "model_name": "GPT-4.1",
      "model_provider": "openai",
      "input_tokens": 500,
      "output_tokens": 200,
      "total_tokens": 700,
      "cost": 0.0014,
      "created_at": "2026-03-24T10:00:00Z"
    }
  ],
  "period_days": 7,
  "total_returned": 1
}
```

**비고:** `user_nickname`이 없는 경우 `user_id` 앞 8자리로 대체.

---

### `GET /api/admin/monitoring/logs/{log_id}`

**설명:** 특정 토큰 사용 로그의 상세 정보 반환.

**인증:** Bearer JWT + `admin` 역할 이상

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `log_id` | int | `token_usage_logs.id` |

**응답 (200):**
```json
{
  "id": 1,
  "input_tokens": 500,
  "output_tokens": 200,
  "total_tokens": 700,
  "cost": 0.0014,
  "created_at": "2026-03-24T10:00:00Z",
  "session_id": "uuid"
}
```

**에러:**
- `404`: 로그를 찾을 수 없음

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
