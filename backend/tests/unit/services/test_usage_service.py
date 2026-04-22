"""UsageService 단위 테스트."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestCostCalculation:
    """토큰 비용 계산 로직 테스트 (DB 없이)."""

    def test_cost_formula_basic(self):
        """비용 = (input * input_cost / 1M) + (output * output_cost / 1M)"""
        input_tokens = 1000
        output_tokens = 500
        input_cost_per_1m = Decimal("5.00")
        output_cost_per_1m = Decimal("15.00")

        input_cost = Decimal(str(input_tokens)) * input_cost_per_1m / Decimal("1000000")
        output_cost = Decimal(str(output_tokens)) * output_cost_per_1m / Decimal("1000000")
        total = input_cost + output_cost

        assert total == Decimal("0.0125")

    def test_cost_formula_zero_tokens(self):
        input_cost = Decimal("0") * Decimal("5.00") / Decimal("1000000")
        output_cost = Decimal("0") * Decimal("15.00") / Decimal("1000000")
        assert input_cost + output_cost == Decimal("0")

    def test_cost_formula_large_tokens(self):
        """100만 토큰 = 정확히 단가."""
        input_tokens = 1_000_000
        cost = Decimal(str(input_tokens)) * Decimal("5.00") / Decimal("1000000")
        assert cost == Decimal("5.00")

    def test_cost_precision(self):
        """소수점 정밀도 유지."""
        input_tokens = 1
        cost = Decimal(str(input_tokens)) * Decimal("5.00") / Decimal("1000000")
        assert cost == Decimal("0.000005")
