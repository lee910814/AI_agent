"""DebateToolExecutor 단위 테스트 — 4가지 서버 실행형 툴 검증."""

import pytest

from app.services.debate.tool_executor import DebateToolExecutor, ToolContext


def _ctx(**kwargs) -> ToolContext:
    """테스트용 ToolContext 생성 헬퍼."""
    defaults = dict(turn_number=3, max_turns=6, speaker="agent_a")
    defaults.update(kwargs)
    return ToolContext(**defaults)


@pytest.fixture
def executor() -> DebateToolExecutor:
    return DebateToolExecutor()


# ─── calculator ──────────────────────────────────────────────────────────────


class TestCalculator:
    def test_basic_addition(self, executor):
        r = executor.execute("calculator", "1 + 2", _ctx())
        assert r.error is None
        assert r.result == "3"

    def test_subtraction(self, executor):
        r = executor.execute("calculator", "10 - 4", _ctx())
        assert r.error is None
        assert r.result == "6"

    def test_multiplication(self, executor):
        r = executor.execute("calculator", "7 * 8", _ctx())
        assert r.error is None
        assert r.result == "56"

    def test_division_returns_float_as_int_when_whole(self, executor):
        r = executor.execute("calculator", "9 / 3", _ctx())
        assert r.error is None
        assert r.result == "3"

    def test_division_returns_float(self, executor):
        r = executor.execute("calculator", "10 / 4", _ctx())
        assert r.error is None
        assert float(r.result) == pytest.approx(2.5)

    def test_power(self, executor):
        r = executor.execute("calculator", "2 ** 10", _ctx())
        assert r.error is None
        assert r.result == "1024"

    def test_modulo(self, executor):
        r = executor.execute("calculator", "10 % 3", _ctx())
        assert r.error is None
        assert r.result == "1"

    def test_floor_division(self, executor):
        r = executor.execute("calculator", "10 // 3", _ctx())
        assert r.error is None
        assert r.result == "3"

    def test_unary_negation(self, executor):
        r = executor.execute("calculator", "-(3 + 2)", _ctx())
        assert r.error is None
        assert r.result == "-5"

    def test_complex_expression(self, executor):
        r = executor.execute("calculator", "(2 + 3) * (10 - 4)", _ctx())
        assert r.error is None
        assert r.result == "30"

    def test_empty_expression_returns_error(self, executor):
        r = executor.execute("calculator", "", _ctx())
        assert r.error is not None
        assert r.result == ""

    def test_whitespace_only_returns_error(self, executor):
        r = executor.execute("calculator", "   ", _ctx())
        assert r.error is not None

    def test_division_by_zero_returns_error(self, executor):
        r = executor.execute("calculator", "1 / 0", _ctx())
        assert r.error is not None
        assert "zero" in r.error.lower()

    def test_function_call_blocked(self, executor):
        """AST 화이트리스트 — 함수 호출 차단."""
        r = executor.execute("calculator", "abs(-1)", _ctx())
        assert r.error is not None

    def test_import_blocked(self, executor):
        """AST 화이트리스트 — import 구문 차단."""
        r = executor.execute("calculator", "__import__('os').system('echo hi')", _ctx())
        assert r.error is not None

    def test_string_constant_blocked(self, executor):
        """문자열 상수는 허용 타입이 아님."""
        r = executor.execute("calculator", "'hello'", _ctx())
        assert r.error is not None

    def test_overflow_returns_error(self, executor):
        r = executor.execute("calculator", "2 ** 100000", _ctx())
        assert r.error is not None


# ─── stance_tracker ──────────────────────────────────────────────────────────


class TestStanceTracker:
    def test_no_previous_claims(self, executor):
        r = executor.execute("stance_tracker", "", _ctx())
        assert r.error is None
        assert "No previous" in r.result

    def test_returns_own_claims(self, executor):
        ctx = _ctx(my_previous_claims=["AI는 유익하다", "비용이 절감된다"])
        r = executor.execute("stance_tracker", "", ctx)
        assert r.error is None
        assert "Turn 1" in r.result
        assert "AI는 유익하다" in r.result
        assert "Turn 2" in r.result
        assert "비용이 절감된다" in r.result

    def test_long_claim_is_truncated(self, executor):
        long_claim = "A" * 500
        ctx = _ctx(my_previous_claims=[long_claim])
        r = executor.execute("stance_tracker", "", ctx)
        assert r.error is None
        # 원본 길이보다 짧고 말줄임표가 붙음
        assert "..." in r.result
        assert len(r.result) < len(long_claim) + 50

    def test_does_not_return_opponent_claims(self, executor):
        ctx = _ctx(
            my_previous_claims=["내 주장"],
            opponent_previous_claims=["상대방 주장"],
        )
        r = executor.execute("stance_tracker", "", ctx)
        assert "상대방 주장" not in r.result
        assert "내 주장" in r.result


# ─── opponent_summary ─────────────────────────────────────────────────────────


class TestOpponentSummary:
    def test_no_opponent_claims(self, executor):
        r = executor.execute("opponent_summary", "", _ctx())
        assert r.error is None
        assert "not made" in r.result.lower() or "no" in r.result.lower()

    def test_returns_opponent_claims(self, executor):
        ctx = _ctx(opponent_previous_claims=["상대방 1번 주장", "상대방 2번 주장"])
        r = executor.execute("opponent_summary", "", ctx)
        assert r.error is None
        assert "Turn 1" in r.result
        assert "상대방 1번 주장" in r.result
        assert "Turn 2" in r.result
        assert "상대방 2번 주장" in r.result

    def test_long_opponent_claim_truncated(self, executor):
        long_claim = "B" * 500
        ctx = _ctx(opponent_previous_claims=[long_claim])
        r = executor.execute("opponent_summary", "", ctx)
        assert "..." in r.result

    def test_does_not_return_own_claims(self, executor):
        ctx = _ctx(
            my_previous_claims=["나의 주장"],
            opponent_previous_claims=["상대 주장"],
        )
        r = executor.execute("opponent_summary", "", ctx)
        assert "나의 주장" not in r.result
        assert "상대 주장" in r.result


# ─── turn_info ───────────────────────────────────────────────────────────────


class TestTurnInfo:
    def test_returns_turn_state(self, executor):
        ctx = _ctx(
            turn_number=3,
            max_turns=6,
            speaker="agent_a",
            my_previous_claims=["c1", "c2"],
            opponent_previous_claims=["o1"],
            my_penalty_total=5,
        )
        r = executor.execute("turn_info", "", ctx)
        assert r.error is None
        assert "3" in r.result  # current turn
        assert "6" in r.result  # max turns
        assert "3" in r.result  # remaining = 6-3 = 3
        assert "5" in r.result  # penalty total
        assert "2" in r.result  # my turns taken
        assert "1" in r.result  # opponent turns

    def test_remaining_turns_calculated_correctly(self, executor):
        ctx = _ctx(turn_number=5, max_turns=6)
        r = executor.execute("turn_info", "", ctx)
        assert r.error is None
        assert "1" in r.result  # remaining = 6-5 = 1

    def test_no_penalty_shows_zero(self, executor):
        ctx = _ctx(my_penalty_total=0)
        r = executor.execute("turn_info", "", ctx)
        assert r.error is None
        assert "0" in r.result


# ─── 알 수 없는 툴 ───────────────────────────────────────────────────────────


class TestUnknownTool:
    def test_unknown_tool_returns_error(self, executor):
        r = executor.execute("nonexistent_tool", "", _ctx())
        assert r.error is not None
        assert "Unknown tool" in r.error
        assert "nonexistent_tool" in r.error

    def test_unknown_tool_lists_available(self, executor):
        r = executor.execute("bad_tool", "", _ctx())
        assert "calculator" in r.error
        assert "stance_tracker" in r.error
        assert "opponent_summary" in r.error
        assert "turn_info" in r.error
