# DebateJudge

> LLM 2-stage 방식 토론 최종 판정기

**파일 경로:** `backend/app/services/debate/judge.py`
**최종 수정일:** 2026-03-17

---

## 모듈 목적

모든 턴이 완료된 후 전체 토론 트랜스크립트를 읽고 LLM 2-stage 방식으로 두 에이전트를 채점하여 승패를 결정한다.

2-stage 설계 이유: Stage 1에서 숫자·점수 언급 없이 서술형 분석을 먼저 생성하여 Stage 2의 앵커링 편향(숫자를 먼저 보면 그 숫자에 매몰되는 현상)을 차단한다.

---

## 채점 기준

`SCORING_CRITERIA` (총 100점 만점):

```python
SCORING_CRITERIA = {
    "argumentation": 40,  # 주장·근거·추론의 일체 (logic + evidence 통합)
    "rebuttal": 35,       # 상대 논거에 대한 직접 대응
    "strategy": 25,       # 쟁점 주도력, 논점 우선순위 설정, 흐름 운영
}
```

상세 채점 기준은 `docs/architecture/06-scoring-system.md` 참조.

---

## 클래스: DebateJudge

### 생성자

```python
def __init__(self, client: InferenceClient | None = None) -> None
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `client` | `InferenceClient \| None` | 외부 주입 시 커넥션 풀 재사용. `None`이면 내부 생성 |

`engine.py`의 `DebateEngine._run_with_client()`에서 공유 `InferenceClient`를 주입해 인스턴스화한다.

### 공개 메서드

#### `generate_intro(topic, agent_a_name, agent_b_name) -> dict`

토론 시작 전 Judge LLM이 생성하는 환영 인사 + 주제 브리핑 (2026-03-23 추가).

**반환값:**
```python
{
    "message": str,        # 한국어 환영 인사 + 주제 요약 (2-3문장)
    "model_id": str,
    "input_tokens": int,
    "output_tokens": int,
    "fallback_reason": str | None,  # LLM 실패 시 폴백 사유
}
```

`engine.py`에서 `judge_intro` SSE 이벤트로 발행되며, 에이전트 턴이 시작되기 전에 관전자에게 표시된다.

---

#### `judge(match, turns, topic, agent_a_name, agent_b_name) -> dict`

LLM으로 토론 판정. 스코어카드 dict 반환.

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `match` | `DebateMatch` | `penalty_a`, `penalty_b`, `agent_a_id`, `agent_b_id` 참조 |
| `turns` | `list[DebateTurnLog]` | 전체 턴 로그 목록 |
| `topic` | `DebateTopic` | `title`, `description` 참조 |
| `agent_a_name` | `str` | 에이전트 A 표시명 (기본: "에이전트 A") |
| `agent_b_name` | `str` | 에이전트 B 표시명 (기본: "에이전트 B") |

**반환값:**

```python
{
    "scorecard": {
        "agent_a": {"argumentation": int, "rebuttal": int, "strategy": int},
        "agent_b": {"argumentation": int, "rebuttal": int, "strategy": int},
        "reasoning": str,  # 한국어 채점 근거
    },
    "score_a": int,      # 벌점 차감 후 최종 점수 (0 이상)
    "score_b": int,
    "penalty_a": int,    # match.penalty_a
    "penalty_b": int,    # match.penalty_b
    "winner_id": UUID | None,  # 점수차 < debate_draw_threshold이면 None (무승부)
    "input_tokens": int,       # Stage 1 + Stage 2 합산
    "output_tokens": int,
    "model_id": str,
}
```

---

## 내부 메서드

### `_judge_with_model(..., model_id) -> dict`

지정된 `model_id`로 2-stage LLM 판정을 수행한다.

**Stage 1: 서술형 분석**

```
JUDGE_ANALYSIS_PROMPT 사용
- 온도: 0.3
- 요청: 논거 명확성, 반박 정확성, 전략적 접근을 서술형으로 분석
- 금지: 숫자·점수 언급 (앵커링 편향 차단)
```

**Stage 2: 분석 기반 채점**

```
JUDGE_SCORING_PROMPT 사용
- 입력: [토론 전문] + [Stage 1 분석 결과]
- 출력: JSON 형식 스코어카드
- 온도: settings.debate_judge_temperature
```

**점수 클램핑:**

```python
for key, max_val in SCORING_CRITERIA.items():
    scorecard["agent_a"][key] = max(0, min(scorecard["agent_a"].get(key, 0), max_val))
    scorecard["agent_b"][key] = max(0, min(scorecard["agent_b"].get(key, 0), max_val))
```

**score 합산 (score overflow 방지, 2026-03-24):**

```python
# SCORING_CRITERIA 키만 합산 — LLM이 extra key를 추가해도 100점 초과 방지
score_a = sum(scorecard["agent_a"].get(k, 0) for k in SCORING_CRITERIA)
score_b = sum(scorecard["agent_b"].get(k, 0) for k in SCORING_CRITERIA)
```

> 이전 코드 `sum(scorecard["agent_a"].values())`는 LLM이 `SCORING_CRITERIA`에 없는 extra key를 추가할 경우 점수가 100점을 초과하는 버그가 있었다. `SCORING_CRITERIA` 키만 명시적으로 합산하도록 수정됨.

**파싱 실패 폴백:**

```python
half_scores = {k: v // 2 for k, v in SCORING_CRITERIA.items()}
# → {"argumentation": 20, "rebuttal": 17, "strategy": 12}
```

### `_format_debate_log(turns, topic, agent_a_name, agent_b_name) -> str`

턴 로그를 Judge LLM 입력용 텍스트로 포맷한다.

- 토론 주제 및 설명 헤더 포함
- 각 턴: `[턴 N] 에이전트명 (찬성/반대) (action):`, 주장, 근거, 벌점 내역
- 마지막에 `[벌점 요약]` 섹션 포함 (에이전트별 위반 유형 횟수)
- 벌점 라벨은 `PENALTY_KO_LABELS` 한국어 변환 (Judge LLM에 영문 파라미터명 노출 방지)

### `_format_violation_summary(name, violations) -> str`

에이전트 이름과 위반 횟수 dict를 받아 Judge용 요약 문자열을 반환한다.

---

## 모델 선택

```python
model_id = settings.debate_judge_model or settings.debate_orchestrator_model
```

`_infer_provider(model_id)` 함수로 모델 ID 접두사를 보고 provider를 추론한다.
- `claude` 접두사 → `anthropic`
- `gemini` 접두사 → `google`
- 나머지 → `openai`

판정은 항상 플랫폼 API 키(`_platform_api_key(provider)`)를 사용한다.

---

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| JSON 파싱 실패 | 각 항목 최대값의 절반으로 균등 점수 → 사실상 무승부 |
| `scorecard` 구조 오류 (`agent_a`/`agent_b`가 dict 아님) | `ValueError` → 파싱 실패로 처리 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `settings` | `app.core.config` | judge 모델, 타임아웃, 온도, 무승부 임계값 |
| `DebateMatch` | `app.models.debate_match` | `penalty_a`, `penalty_b`, `agent_a_id`, `agent_b_id` |
| `DebateTopic` | `app.models.debate_topic` | `title`, `description` |
| `DebateTurnLog` | `app.models.debate_turn_log` | 턴별 발언·벌점 |
| `InferenceClient` | `app.services.llm.inference_client` | LLM API 호출 |

### 관련 설정값 (`config.py`)

| 설정 키 | 설명 |
|---|---|
| `debate_judge_model` | 판정 LLM 모델 ID (기본: `gpt-4.1`) |
| `debate_judge_max_tokens` | judge LLM 최대 출력 토큰 |
| `debate_judge_temperature` | Stage 2 채점 온도 |
| `debate_draw_threshold` | 무승부 판정 최소 점수차 기준 (기본: 5) |

---

## 호출 흐름

```
engine.py (DebateEngine._run_with_client)
  → DebateJudge(client=client)
  → judge_instance.judge(match, turns, topic, agent_a_name, agent_b_name)
      → _judge_with_model(match, turns, topic, ..., model_id)
          → _format_debate_log(turns, topic, ...)
          → Stage 1: InferenceClient.generate_byok(JUDGE_ANALYSIS_PROMPT)
          → Stage 2: InferenceClient.generate_byok(JUDGE_SCORING_PROMPT + 분석결과)
          → 점수 클램핑 → 벌점 차감 → 승패 결정
  → MatchFinalizer.finalize(match, judgment, ...)
```

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-24 | v1.2 | score 합산 방식 변경 (`values()` → `SCORING_CRITERIA` 키 명시) — score overflow 방지 버그 수정 |
| 2026-03-23 | v1.1 | `generate_intro()` 추가 — 토론 시작 전 Judge LLM 환영 인사 + 주제 브리핑 |
| 2026-03-17 | v1.0 | 신규 작성. judge.py 분리 반영. 2-stage 판정, 현행 채점 기준(argumentation/rebuttal/strategy) 문서화 |
