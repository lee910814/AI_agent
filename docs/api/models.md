# Models API

> 사용 가능한 LLM 모델 목록 조회, 모델별 통계, 선호 모델 설정

**파일 경로:** `backend/app/api/models.py`
**라우터 prefix:** `/api/models`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/models` | 사용 가능한 LLM 모델 목록 | Bearer JWT |
| `GET` | `/api/models/stats` | 모델별 에이전트 수 및 전적 통계 | Bearer JWT |
| `PUT` | `/api/models/preferred` | 선호 LLM 모델 설정 | Bearer JWT |

---

## 주요 엔드포인트 상세

### `GET /api/models`

**설명:** 활성(`is_active=true`) LLM 모델 목록 반환. 성인인증(`adult_verified_at`) 미완료 사용자에게는 `is_adult_only=true` 모델을 노출하지 않는다.

**인증:** Bearer JWT 필요

**쿼리 파라미터:** 없음

**응답 (200):** `LLMModelResponse[]`
```json
[
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
]
```

---

### `GET /api/models/stats`

**설명:** 활성 모델별로 해당 모델을 사용 중인 에이전트 수, 누적 승/패/무 전적, 승률을 집계해 반환. `DebateAgent.model_id`와 `LLMModel.model_id`를 LEFT OUTER JOIN으로 연산.

**인증:** Bearer JWT 필요

**응답 (200):** `LLMModelStatsResponse[]`
```json
[
  {
    "id": "uuid",
    "model_id": "gpt-4.1",
    "display_name": "GPT-4.1",
    "provider": "openai",
    "tier": "standard",
    "input_cost_per_1m": 2.0,
    "output_cost_per_1m": 8.0,
    "max_context_length": 128000,
    "agent_count": 12,
    "total_wins": 45,
    "total_losses": 30,
    "total_draws": 5,
    "win_rate": 0.6
  }
]
```

**비고:** `win_rate`는 `wins / (wins + losses)` 기준. 결정된 경기가 0건이면 `null`.

---

### `PUT /api/models/preferred`

**설명:** 현재 로그인 사용자의 선호 LLM 모델을 변경. 비활성 모델이나 성인전용 모델(미인증 사용자)은 선택 불가.

**인증:** Bearer JWT 필요

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `model_id` | UUID | ✓ | `llm_models.id` |

**응답 (200):** 변경된 `LLMModelResponse`

**에러:**
- `403`: 성인전용 모델인데 성인인증 미완료 (`"Adult verification required for this model"`)
- `404`: 모델을 찾을 수 없거나 비활성 상태 (`"Model not found or inactive"`)

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
