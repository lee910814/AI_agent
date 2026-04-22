# LLMModel

> 플랫폼에서 사용 가능한 LLM 모델 설정 및 비용 정보 — `InferenceClient`가 이 테이블을 조회해 provider와 비용을 결정한다

**파일 경로:** `backend/app/models/llm_model.py`
**테이블명:** `llm_models`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `provider` | VARCHAR(30) | NOT NULL | — | LLM 공급사 식별자 (openai / anthropic / google / runpod 등) |
| `model_id` | VARCHAR(100) | NOT NULL | — | 공급사 API 모델 식별자 문자열 |
| `display_name` | VARCHAR(100) | NOT NULL | — | 사용자 화면 표시 이름 |
| `input_cost_per_1m` | NUMERIC(10,4) | NOT NULL | — | 입력 토큰 1M당 비용 (USD) |
| `output_cost_per_1m` | NUMERIC(10,4) | NOT NULL | — | 출력 토큰 1M당 비용 (USD) |
| `max_context_length` | INTEGER | NOT NULL | — | 최대 컨텍스트 토큰 수 |
| `is_adult_only` | BOOLEAN | NOT NULL | false | 성인 전용 모델 여부 |
| `is_active` | BOOLEAN | NOT NULL | true | 활성 모델 여부 (비활성 시 신규 에이전트 선택 불가) |
| `tier` | VARCHAR(20) | NOT NULL | 'economy' | 모델 티어 (economy / standard / premium) |
| `credit_per_1k_tokens` | INTEGER | NOT NULL | 1 | 1,000토큰당 차감 크레딧 |
| `metadata` | JSONB | NULL | — | 추가 메타데이터 (Python 속성명: `metadata_`) |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 모델 등록 시각 |

---

## 관계 (Relationships)

이 모델에서 직접 정의된 relationship 없음.
역방향으로 `User.preferred_llm_model`과 `TokenUsageLog.llm_model`이 이 모델을 참조한다.

---

## 인덱스 / 제약 조건

```sql
-- provider + model_id 조합 유니크 (동일 공급사에서 동일 모델 중복 등록 방지)
CONSTRAINT uq_llm_provider_model
    UNIQUE (provider, model_id)

CONSTRAINT ck_llm_tier
    CHECK (tier IN ('economy', 'standard', 'premium'))
```

---

## 비고

- Python 코드에서 `metadata` 컬럼은 SQLAlchemy 예약어 충돌 방지를 위해 `metadata_`로 접근한다
  (`mapped_column("metadata", JSONB)` 형태로 매핑)

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
