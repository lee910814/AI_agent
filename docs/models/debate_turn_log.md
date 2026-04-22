# DebateTurnLog

> 매치 각 턴의 에이전트 발언·LLM 검토 결과·패널티·토큰 사용량을 기록하는 로그 테이블

**파일 경로:** `backend/app/models/debate_turn_log.py`
**테이블명:** `debate_turn_logs`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `match_id` | UUID | NOT NULL | — | 소속 매치 FK → `debate_matches.id` ON DELETE CASCADE |
| `turn_number` | INTEGER | NOT NULL | — | 매치 내 순차 턴 번호 |
| `speaker` | VARCHAR(10) | NOT NULL | — | 발언 에이전트 구분 (agent_a / agent_b) |
| `agent_id` | UUID | NOT NULL | — | 발언 에이전트 FK → `debate_agents.id` ON DELETE CASCADE |
| `action` | VARCHAR(20) | NOT NULL | — | 발언 행동 유형 (argue / rebut / concede / question / summarize) |
| `claim` | TEXT | NOT NULL | — | 에이전트 주장 본문 |
| `evidence` | TEXT | NULL | — | 주장 근거 텍스트 |
| `tool_used` | VARCHAR(50) | NULL | — | 사용된 Tool Call 이름 |
| `tool_result` | TEXT | NULL | — | Tool Call 실행 결과 텍스트 |
| `raw_response` | JSONB | NULL | — | LLM 원시 응답 |
| `penalties` | JSONB | NULL | — | 규칙 위반 패널티 항목 `{규칙명: 점수}` |
| `penalty_total` | INTEGER | NOT NULL | 0 | 패널티 합계 점수 |
| `review_result` | JSONB | NULL | — | LLM 검토 결과 (논리·허위·주제이탈 점수 등) |
| `is_blocked` | BOOLEAN | NOT NULL | false | 검토 결과 발언 차단 여부 |
| `human_suspicion_score` | INTEGER | NOT NULL | 0 | 인간 개입 의심 점수 (0~100) |
| `response_time_ms` | INTEGER | NULL | — | LLM 응답 소요 시간 (밀리초) |
| `input_tokens` | INTEGER | NOT NULL | 0 | LLM 입력 토큰 수 |
| `output_tokens` | INTEGER | NOT NULL | 0 | LLM 출력 토큰 수 |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 턴 로그 생성 시각 |

---

## 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `match` | DebateMatch | ManyToOne | 소속 매치 (`back_populates="turns"`) |
| `agent` | DebateAgent | ManyToOne | 발언한 에이전트 |

---

## 인덱스 / 제약 조건

```sql
CONSTRAINT ck_debate_turn_logs_speaker
    CHECK (speaker IN ('agent_a', 'agent_b'))

CONSTRAINT ck_debate_turn_logs_action
    CHECK (action IN ('argue', 'rebut', 'concede', 'question', 'summarize'))

-- FK
match_id → debate_matches.id  ON DELETE CASCADE
agent_id → debate_agents.id   ON DELETE CASCADE
```

---

## 비고

- `review_result` JSONB 구조 예시:
  ```json
  {
    "logic_score": 7,
    "violations": ["llm_off_topic"],
    "penalty": 5,
    "reasoning": "주제와 무관한 내용 포함"
  }
  ```
- `penalties` JSONB 키 접두사 규칙:
  - regex 기반 벌점: 접두사 없음 (예: `prompt_injection`, `ad_hominem`)
  - LLM 검토 기반 벌점: `llm_` 접두사 (예: `llm_off_topic`, `llm_false_claim`)

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
