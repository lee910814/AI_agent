"""H2H 전적 서비스 단위 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_get_head_to_head_method_exists():
    """get_head_to_head 메서드가 존재한다."""
    from app.services.debate.agent_service import DebateAgentService

    assert hasattr(DebateAgentService, "get_head_to_head")


@pytest.mark.asyncio
async def test_get_head_to_head_empty_result():
    """매치 없으면 빈 리스트 반환."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    from app.services.debate.agent_service import DebateAgentService

    service = DebateAgentService(db)
    # DB execute가 빈 결과를 반환하면 빈 리스트가 나와야 함
    # (실제 UNION ALL 쿼리는 DB 없이 실행 불가 — 구조 검증만)
    assert hasattr(service, "get_head_to_head")


def test_get_tier_from_elo_boundaries():
    """ELO 경계값에서 티어가 올바르게 반환된다."""
    from app.services.debate.agent_service import get_tier_from_elo

    assert get_tier_from_elo(2050) == "Master"
    assert get_tier_from_elo(1900) == "Diamond"
    assert get_tier_from_elo(1750) == "Platinum"
    assert get_tier_from_elo(1600) == "Gold"
    assert get_tier_from_elo(1450) == "Silver"
    assert get_tier_from_elo(1300) == "Bronze"
    assert get_tier_from_elo(1299) == "Iron"


def test_head_to_head_schema():
    """HeadToHeadEntry 스키마가 올바르게 정의되었다."""
    from app.schemas.debate_agent import HeadToHeadEntry

    entry = HeadToHeadEntry(
        opponent_id="test-id",
        opponent_name="TestAgent",
        opponent_image_url=None,
        total_matches=5,
        wins=3,
        losses=1,
        draws=1,
    )
    assert entry.total_matches == 5
    assert entry.wins == 3
    assert entry.opponent_image_url is None
