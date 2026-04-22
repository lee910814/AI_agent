"""토론 에이전트 서버 실행 툴셋.

외부 API 호출 없이 EC2 로컬에서 처리하는 4가지 무료 툴.
- calculator     : AST 기반 안전 수식 계산
- stance_tracker : 에이전트 본인 이전 주장 조회
- opponent_summary: 상대방 주장 요약
- turn_info      : 현재 게임 상태 조회
"""

import ast
import logging
import operator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

AVAILABLE_TOOLS = ["calculator", "stance_tracker", "opponent_summary", "turn_info"]

# 계산기 허용 연산자 (화이트리스트) — eval 없이 AST로 직접 계산
_SAFE_OPS: dict = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# 허용 노드 타입
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.USub, ast.UAdd,
)

# 주장 미리보기 최대 길이 (토큰 절약)
_CLAIM_PREVIEW_LEN = 300


@dataclass
class ToolContext:
    """툴 실행에 필요한 현재 턴 문맥.

    Attributes:
        turn_number: 현재 턴 번호.
        max_turns: 매치 최대 턴 수.
        speaker: 현재 발언자 ('agent_a' | 'agent_b').
        my_previous_claims: 본인의 이전 발언 목록.
        opponent_previous_claims: 상대방의 이전 발언 목록.
        my_penalty_total: 현재까지 누적된 본인 벌점.
    """

    turn_number: int
    max_turns: int
    speaker: str
    my_previous_claims: list[str] = field(default_factory=list)
    opponent_previous_claims: list[str] = field(default_factory=list)
    my_penalty_total: int = 0


@dataclass
class ToolResult:
    """툴 실행 결과.

    Attributes:
        result: 툴 실행 결과 문자열. 실패 시 빈 문자열.
        error: 에러 메시지. None이면 성공.
    """

    result: str
    error: str | None = None


class DebateToolExecutor:
    """서버 측 툴 실행기. 에이전트의 tool_request를 받아 결과를 반환.

    WebSocket 경유 로컬 에이전트가 턴 실행 중 툴 호출을 요청하면
    WSConnectionManager가 이 실행기를 통해 처리한다.
    """

    def execute(self, tool_name: str, tool_input: str, ctx: ToolContext) -> ToolResult:
        """툴 이름으로 디스패치하여 실행한다.

        Args:
            tool_name: 실행할 툴 이름 ('calculator' | 'stance_tracker' | 등).
            tool_input: 툴 입력값 (calculator이면 수식, 나머지는 무시됨).
            ctx: 현재 턴 문맥.

        Returns:
            ToolResult. 알 수 없는 툴이면 error 필드에 메시지를 포함한 ToolResult 반환.
        """
        if tool_name == "calculator":
            return self._run_calculator(tool_input)
        elif tool_name == "stance_tracker":
            return self._run_stance_tracker(ctx)
        elif tool_name == "opponent_summary":
            return self._run_opponent_summary(ctx)
        elif tool_name == "turn_info":
            return self._run_turn_info(ctx)
        else:
            available = ", ".join(AVAILABLE_TOOLS)
            return ToolResult(
                result="",
                error=f"Unknown tool '{tool_name}'. Available tools: {available}",
            )

    # ── 툴 구현 ───────────────────────────────────────────────────────────────

    def _run_calculator(self, expr: str) -> ToolResult:
        """수식 안전 계산.

        AST 화이트리스트 방식으로 코드 인젝션 방지.
        허용: +, -, *, /, **, %, //,  정수/실수 상수, 괄호
        금지: 함수 호출, 변수, import, 속성 접근
        """
        if not expr or not expr.strip():
            return ToolResult(result="", error="Expression is empty")
        try:
            tree = ast.parse(expr.strip(), mode="eval")
            # 모든 노드가 허용 목록에 있는지 검사
            for node in ast.walk(tree):
                if not isinstance(node, _ALLOWED_NODES):
                    return ToolResult(
                        result="",
                        error=f"Unsupported operation in expression: {type(node).__name__}",
                    )
            value = self._eval_node(tree.body)
            # 부동소수점이 정수와 같으면 정수로 표시 (예: 4.0 → 4)
            if isinstance(value, float) and value == int(value):
                value = int(value)
            return ToolResult(result=str(value))
        except ZeroDivisionError:
            return ToolResult(result="", error="Division by zero")
        except OverflowError:
            return ToolResult(result="", error="Result is too large to compute")
        except (ValueError, TypeError) as exc:
            return ToolResult(result="", error=f"Calculation error: {exc}")
        except Exception as exc:
            return ToolResult(result="", error=f"Invalid expression: {exc}")

    def _eval_node(self, node: ast.expr) -> float | int:
        """재귀적으로 AST 노드를 평가하여 수식 결과를 반환한다.

        Args:
            node: 평가할 AST 표현식 노드.

        Returns:
            계산 결과 (int 또는 float).

        Raises:
            TypeError: 화이트리스트에 없는 노드 타입 또는 상수 타입인 경우.
            ZeroDivisionError: 0으로 나누는 경우.
        """
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, int | float):
                raise TypeError(f"Unsupported constant type: {type(node.value).__name__}")
            return node.value
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPS:
                raise TypeError(f"Unsupported operator: {op_type.__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return _SAFE_OPS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPS:
                raise TypeError(f"Unsupported unary operator: {op_type.__name__}")
            operand = self._eval_node(node.operand)
            return _SAFE_OPS[op_type](operand)
        else:
            raise TypeError(f"Unsupported AST node type: {type(node).__name__}")

    def _run_stance_tracker(self, ctx: ToolContext) -> ToolResult:
        """내 이전 주장 목록을 반환한다. 자기 모순 감지 및 일관성 유지용.

        Args:
            ctx: 현재 턴 문맥.

        Returns:
            'Turn N: 발언...' 형식의 ToolResult.
        """
        if not ctx.my_previous_claims:
            return ToolResult(result="No previous claims recorded yet.")
        lines = [
            f"Turn {i + 1}: {claim[:_CLAIM_PREVIEW_LEN]}"
            + ("..." if len(claim) > _CLAIM_PREVIEW_LEN else "")
            for i, claim in enumerate(ctx.my_previous_claims)
        ]
        return ToolResult(result="\n".join(lines))

    def _run_opponent_summary(self, ctx: ToolContext) -> ToolResult:
        """상대방의 이전 주장을 요약하여 반환한다. LLM 호출 없이 텍스트 정리만.

        Args:
            ctx: 현재 턴 문맥.

        Returns:
            상대방 주장 목록이 담긴 ToolResult.
        """
        if not ctx.opponent_previous_claims:
            return ToolResult(result="Opponent has not made any claims yet.")
        lines = [
            f"- (Turn {i + 1}) {claim[:_CLAIM_PREVIEW_LEN]}"
            + ("..." if len(claim) > _CLAIM_PREVIEW_LEN else "")
            for i, claim in enumerate(ctx.opponent_previous_claims)
        ]
        return ToolResult(result="Opponent's claims so far:\n" + "\n".join(lines))

    def _run_turn_info(self, ctx: ToolContext) -> ToolResult:
        """현재 게임 상태 정보를 반환한다. 전략 수립용.

        Args:
            ctx: 현재 턴 문맥.

        Returns:
            현재 턴, 남은 턴, 누적 벌점 등이 담긴 ToolResult.
        """
        remaining = ctx.max_turns - ctx.turn_number
        info_lines = [
            f"Current turn    : {ctx.turn_number} / {ctx.max_turns}",
            f"Remaining turns : {remaining}",
            f"My penalty total: {ctx.my_penalty_total}",
            f"My turns taken  : {len(ctx.my_previous_claims)}",
            f"Opponent turns  : {len(ctx.opponent_previous_claims)}",
        ]
        return ToolResult(result="\n".join(info_lines))
