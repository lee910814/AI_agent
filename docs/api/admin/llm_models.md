# Admin LLM Models API

> LLM 모델 등록, 수정, 활성/비활성 전환, 사용량 통계 조회

**파일 경로:** `backend/app/api/admin/system/llm_models.py`
**라우터 prefix:** `/api/admin/models`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/admin/models` | 전체 LLM 모델 목록 (비활성 포함) | admin 이상 |
| `POST` | `/api/admin/models` | LLM 모델 등록 | superadmin |
| `PUT` | `/api/admin/models/{model_id}` | LLM 모델 정보/비용 수정 | superadmin |
| `PUT` | `/api/admin/models/{model_id}/toggle` | 모델 활성/비활성 전환 | superadmin |
| `GET` | `/api/admin/models/usage-stats` | 모델별 총 사용량 통계 | admin 이상 |

---

## 주요 엔드포인트 상세

### `GET /api/admin/models`

**설명:** 비활성 모델 포함 전체 LLM 모델 목록. 사용자 대상 `GET /api/models`와 달리 활성 여부와 무관하게 모두 반환. 최신 등록순 정렬.

**인증:** Bearer JWT + `admin` 역할 이상 (`require_admin`)

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
      "provider": "openai",
      "model_id": "gpt-4.1",
      "display_name": "GPT-4.1",
      "tier": "standard",
      "input_cost_per_1m": 2.0,
      "output_cost_per_1m": 8.0,
      "max_context_length": 128000,
      "is_active": true,
      "is_adult_only": false
    }
  ],
  "total": 15
}
```

---

### `POST /api/admin/models`

**설명:** 새 LLM 모델 등록. `superadmin` 전용. 동일 `provider + model_id` 조합이 이미 존재하면 409.

**인증:** Bearer JWT + `superadmin` 역할 (`require_superadmin`)

**요청 바디:** `LLMModelCreate`
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `provider` | string | ✓ | `"openai"` / `"anthropic"` / `"google"` / `"runpod"` |
| `model_id` | string | ✓ | API 호출 시 사용되는 모델 식별자 (예: `"gpt-4.1"`) |
| `display_name` | string | ✓ | UI 표시명 |
| `input_cost_per_1m` | number | ✓ | 입력 1M 토큰당 비용 (USD) |
| `output_cost_per_1m` | number | ✓ | 출력 1M 토큰당 비용 (USD) |
| `max_context_length` | int | ✓ | 최대 컨텍스트 길이 (토큰 수) |
| `tier` | string | ✓ | 모델 등급 (예: `"standard"`, `"premium"`) |
| `is_adult_only` | bool | ✓ | 성인전용 여부 |
| `credit_per_1k_tokens` | number |  | 크레딧 과금 단가 |
| `metadata` | object |  | 기타 메타데이터 |

**응답 (201):** 등록된 `LLMModelResponse`

**에러:**
- `409`: 동일 `provider + model_id` 모델이 이미 존재

---

### `PUT /api/admin/models/{model_id}`

**설명:** 기존 LLM 모델 정보 수정. `superadmin` 전용. 변경된 필드만 전송 가능 (partial update).

**인증:** Bearer JWT + `superadmin` 역할

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `model_id` | UUID | `llm_models.id` |

**요청 바디:** `LLMModelUpdate` (모든 필드 선택)

**응답 (200):** 변경된 `LLMModelResponse`

**에러:**
- `404`: 모델을 찾을 수 없음

---

### `PUT /api/admin/models/{model_id}/toggle`

**설명:** 모델의 `is_active` 상태를 반전. `superadmin` 전용. 비활성화하면 사용자 목록에서 즉시 제외.

**인증:** Bearer JWT + `superadmin` 역할

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `model_id` | UUID | `llm_models.id` |

**응답 (200):** 업데이트된 `LLMModelResponse` (`is_active` 반전됨)

**에러:**
- `404`: 모델을 찾을 수 없음

---

### `GET /api/admin/models/usage-stats`

**설명:** 모델별 누적 토큰 사용량 통계. `token_usage_logs` 테이블을 `llm_model_id`로 그룹핑.

**인증:** Bearer JWT + `admin` 역할 이상

**응답 (200):** `ModelUsageStats[]`
```json
[
  {
    "llm_model_id": "uuid",
    "total_requests": 2500,
    "total_input_tokens": 12500000,
    "total_output_tokens": 5000000,
    "total_cost": 45.0
  }
]
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
