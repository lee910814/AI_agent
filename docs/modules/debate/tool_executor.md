# DebateToolExecutor

> 토론 에이전트가 발언 생성 중 호출하는 4가지 서버 측 툴 실행기

**파일 경로:** `backend/app/services/debate/tool_executor.py`
**최종 수정일:** 2026-03-12

---

## 모듈 목적

토론 에이전트가 발언 생성 중 요청하는 Tool Call을 서버에서 처리한다. 외부 API 호출 없이 EC2 로컬에서만 실행되므로 추가 비용이 발생하지 않는다.

제공하는 4가지 툴은 다음과 같다.

- **`calculator`** — AST 화이트리스트 방식 수식 안전 계산 (코드 인젝션 방지)
- **`stance_tracker`** — 에이전트 본인의 이전 주장 목록 조회 (자기 모순 감지·일관성 유지)
- **`opponent_summary`** — 상대방 이전 주장 텍스트 정리 반환 (LLM 호출 없음)
- **`turn_info`** — 현재 턴 번호, 남은 턴, 누적 벌점 등 게임 상태 조회

---

## 주요 상수

| 상수 | 타입 | 값 / 설명 |
|---|---|---|
| `AVAILABLE_TOOLS` | `list[str]` | `["calculator", "stance_tracker", "opponent_summary", "turn_info"]` — 에이전트가 호출 가능한 툴 목록 |
| `_SAFE_OPS` | `dict` | 계산기 허용 연산자 화이트리스트. `ast.Add → operator.add` 등 8가지 이항·단항 연산자 매핑 |
| `_ALLOWED_NODES` | `tuple` | 계산기 허용 AST 노드 타입. `Expression`, `BinOp`, `UnaryOp`, `Constant` 및 연산자 노드 한정 |
| `_CLAIM_PREVIEW_LEN` | `int` | `300` — `stance_tracker` / `opponent_summary` 주장 미리보기 최대 길이 (토큰 절약) |

---

## 클래스: ToolContext

`@dataclass`. 툴 실행에 필요한 현재 턴 문맥을 담는 값 객체.

### 생성자

```python
@dataclass
class ToolContext:
    turn_number: int
    max_turns: int
    speaker: str
    my_previous_claims: list[str] = field(default_factory=list)
    opponent_previous_claims: list[str] = field(default_factory=list)
    my_penalty_total: int = 0
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `turn_number` | `int` | 현재 턴 번호 |
| `max_turns` | `int` | 매치 최대 턴 수 |
| `speaker` | `str` | 발언자 식별자 (`"agent_a"` / `"agent_b"`) |
| `my_previous_claims` | `list[str]` | 내 이전 주장 목록 (발언 전체 텍스트) |
| `opponent_previous_claims` | `list[str]` | 상대방 이전 주장 목록 |
| `my_penalty_total` | `int` | 내 누적 벌점 합계 |

### 메서드

없음 (순수 데이터 클래스).

---

## 클래스: ToolResult

`@dataclass`. 툴 실행 결과를 담는 값 객체. `error is None`이면 성공.

### 생성자

```python
@dataclass
class ToolResult:
    result: str
    error: str | None = None
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `result` | `str` | 성공 시 결과 문자열. 실패 시 빈 문자열 |
| `error` | `str \| None` | 실패 시 에러 메시지. 성공 시 `None` |

### 메서드

없음 (순수 데이터 클래스).

---

## 클래스: DebateToolExecutor

서버 측 툴 실행기. 에이전트의 `tool_request`를 받아 결과를 반환한다. 인스턴스 상태가 없으므로 재사용 가능하다.

### 생성자

```python
def __init__(self)
```

별도 파라미터 없음. 상태를 보유하지 않는 클래스.

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `execute` | `(tool_name: str, tool_input: str, ctx: ToolContext) -> ToolResult` | 툴 이름으로 내부 메서드에 디스패치. 알 수 없는 툴 이름이면 에러 ToolResult 반환 |
| `_run_calculator` | `(expr: str) -> ToolResult` | AST 화이트리스트 방식으로 수식을 안전하게 계산. 함수 호출·변수·import 등 금지. 부동소수점이 정수와 같으면 정수로 출력 (`4.0 → 4`) |
| `_eval_node` | `(node: ast.expr) -> float \| int` | `_run_calculator`에서 재귀 호출. AST 노드를 직접 평가하며 화이트리스트에 없는 노드는 `TypeError` |
| `_run_stance_tracker` | `(ctx: ToolContext) -> ToolResult` | `ctx.my_previous_claims`를 `Turn N: {텍스트[:300]}` 형식으로 반환. 이전 주장 없으면 안내 메시지 반환 |
| `_run_opponent_summary` | `(ctx: ToolContext) -> ToolResult` | `ctx.opponent_previous_claims`를 `- (Turn N) {텍스트[:300]}` 형식으로 반환. 상대 주장 없으면 안내 메시지 반환 |
| `_run_turn_info` | `(ctx: ToolContext) -> ToolResult` | 현재 턴, 남은 턴, 누적 벌점, 내 턴 수, 상대 턴 수를 포함한 게임 상태 문자열 반환 |

#### `calculator` 허용/금지 사항

| 허용 | 금지 |
|---|---|
| `+`, `-`, `*`, `/`, `**`, `%`, `//` | 함수 호출 (`abs()`, `int()` 등) |
| 정수/실수 상수, 괄호 | 변수 참조, `import`, 속성 접근 |
| 단항 연산자 (`-x`, `+x`) | 문자열, 리스트, 딕셔너리 리터럴 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `ast` | stdlib | 수식 파싱 및 AST 노드 검사 |
| `operator` | stdlib | `_SAFE_OPS` 딕셔너리의 연산자 함수 매핑 |
| `dataclasses` | stdlib | `ToolContext`, `ToolResult` 데이터 클래스 |
| `logging` | stdlib | 모듈 로거 |

---

## 호출 흐름

### 툴 실행 흐름 (로컬 에이전트)

```
engine.py (_execute_turn, local 에이전트)
  → ToolContext 생성 (turn_number, my_previous_claims, opponent_previous_claims 등)
  → DebateToolExecutor 인스턴스 생성
  → ws_manager.request_turn(
        match_id, agent_id, WSTurnRequest,
        tool_executor=DebateToolExecutor(),
        tool_context=ctx
    )

ws_manager.py (_handle_tool_request)
  → DebateToolExecutor.execute(tool_name, tool_input, ctx)
      ├─ "calculator"      → _run_calculator(tool_input)
      ├─ "stance_tracker"  → _run_stance_tracker(ctx)
      ├─ "opponent_summary"→ _run_opponent_summary(ctx)
      ├─ "turn_info"       → _run_turn_info(ctx)
      └─ 알 수 없는 이름    → ToolResult(error="Unknown tool ...")
  → ToolResult → WebSocket "tool_result" 메시지 전송
```

---

## 에러 처리

툴 실행기는 예외를 외부로 전파하지 않는다. 모든 오류는 `ToolResult(result="", error=...)` 형태로 반환된다.

| 상황 | 반환값 |
|---|---|
| 알 수 없는 툴 이름 | `ToolResult(result="", error="Unknown tool '{name}'. Available tools: ...")` |
| 빈 수식 | `ToolResult(result="", error="Expression is empty")` |
| 허용되지 않은 AST 노드 | `ToolResult(result="", error="Unsupported operation in expression: {NodeType}")` |
| 0 나누기 | `ToolResult(result="", error="Division by zero")` |
| OverflowError | `ToolResult(result="", error="Result is too large to compute")` |
| 기타 계산 오류 | `ToolResult(result="", error="Calculation error: {exc}")` |
| 파싱 불가 수식 | `ToolResult(result="", error="Invalid expression: {exc}")` |
| 이전 주장 없음 (stance_tracker) | `ToolResult(result="No previous claims recorded yet.")` |
| 상대 주장 없음 (opponent_summary) | `ToolResult(result="Opponent has not made any claims yet.")` |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-12 | 레퍼런스 형식에 맞춰 전면 재작성. ToolContext/ToolResult를 별도 클래스 섹션으로 분리, 호출 흐름 구체화, 에러 처리 표 상세화 |
| 2026-03-11 | 실제 코드 기반으로 초기 재작성 |
