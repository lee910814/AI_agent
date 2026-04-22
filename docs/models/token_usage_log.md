# TokenUsageLog

> 모든 LLM 호출의 토큰 수와 비용을 기록하는 과금 근거 테이블

**파일 경로:** `backend/app/models/token_usage_log.py`
**테이블명:** `token_usage_logs`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | BIGINT | NOT NULL | autoincrement | PK (BigInteger, 자동 증가) |
| `user_id` | UUID | NOT NULL | — | 호출한 사용자 FK → `users.id` ON DELETE CASCADE |
| `session_id` | UUID | NULL | — | 관련 세션 UUID (FK 없음, 참조용) |
| `llm_model_id` | UUID | NOT NULL | — | 사용한 LLM 모델 FK → `llm_models.id` |
| `input_tokens` | INTEGER | NOT NULL | — | 입력 토큰 수 |
| `output_tokens` | INTEGER | NOT NULL | — | 출력 토큰 수 |
| `cost` | NUMERIC(10,6) | NOT NULL | — | 호출 비용 (USD, 소수점 6자리) |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 호출 시각 |

---

## 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `user` | User | ManyToOne | 호출한 사용자 |
| `llm_model` | LLMModel | ManyToOne | 사용한 LLM 모델 |

---

## 인덱스 / 제약 조건

```sql
-- 사용자별 기간 집계 쿼리 최적화
Index("idx_usage_user", "user_id", "created_at")

-- 모델별 기간 집계 쿼리 최적화
Index("idx_usage_model", "llm_model_id", "created_at")

-- 세션별 조회
Index("idx_usage_session", "session_id")
```

---

## 비고

- PK가 UUID가 아닌 BigInteger autoincrement인 이유: 고빈도 INSERT에서 시퀀스가 UUID gen보다 효율적이기 때문
- `session_id`는 `chat_sessions` 테이블이 없으므로 FK 없이 UUID만 저장 (토론 플랫폼 맥락에서 매치 세션 추적용)
- `cost` 계산: `(input_tokens / 1_000_000) * input_cost_per_1m + (output_tokens / 1_000_000) * output_cost_per_1m`

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
