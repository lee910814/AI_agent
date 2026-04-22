"""예측 투표 서비스 단위 테스트."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_prediction_create_schema():
    """PredictionCreate 스키마 유효성 검증."""
    from app.schemas.debate_match import PredictionCreate

    p = PredictionCreate(prediction="a_win")
    assert p.prediction == "a_win"

    p2 = PredictionCreate(prediction="b_win")
    assert p2.prediction == "b_win"

    p3 = PredictionCreate(prediction="draw")
    assert p3.prediction == "draw"


def test_prediction_create_invalid_value():
    """잘못된 prediction 값은 ValidationError."""
    from pydantic import ValidationError

    from app.schemas.debate_match import PredictionCreate

    with pytest.raises(ValidationError):
        PredictionCreate(prediction="invalid")


def test_prediction_stats_schema():
    """PredictionStats 스키마 기본값 확인."""
    from app.schemas.debate_match import PredictionStats

    stats = PredictionStats()
    assert stats.a_win == 0
    assert stats.b_win == 0
    assert stats.draw == 0
    assert stats.total == 0
    assert stats.my_prediction is None
    assert stats.is_correct is None


@pytest.mark.asyncio
async def test_resolve_predictions_a_win():
    """agent_a 승리 시 a_win 예측이 correct."""
    db = AsyncMock()
    execute_result = MagicMock()
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()

    from app.services.debate.match_service import DebateMatchService

    service = DebateMatchService(db)
    agent_a_id = str(uuid.uuid4())
    agent_b_id = str(uuid.uuid4())

    await service.resolve_predictions(
        match_id="match-1",
        winner_id=agent_a_id,
        agent_a_id=agent_a_id,
        agent_b_id=agent_b_id,
    )

    # execute가 호출되었는지 확인 (UPDATE 쿼리)
    assert db.execute.called
    assert db.commit.called


@pytest.mark.asyncio
async def test_resolve_predictions_draw():
    """무승부 시 draw 예측이 correct."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()

    from app.services.debate.match_service import DebateMatchService

    service = DebateMatchService(db)
    agent_a_id = str(uuid.uuid4())
    agent_b_id = str(uuid.uuid4())

    await service.resolve_predictions(
        match_id="match-1",
        winner_id=None,
        agent_a_id=agent_a_id,
        agent_b_id=agent_b_id,
    )

    assert db.execute.called


@pytest.mark.asyncio
async def test_resolve_predictions_b_win():
    """agent_b 승리 시 b_win 예측이 correct."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    db.commit = AsyncMock()

    from app.services.debate.match_service import DebateMatchService

    service = DebateMatchService(db)
    agent_a_id = str(uuid.uuid4())
    agent_b_id = str(uuid.uuid4())

    await service.resolve_predictions(
        match_id="match-1",
        winner_id=agent_b_id,
        agent_a_id=agent_a_id,
        agent_b_id=agent_b_id,
    )

    assert db.execute.called
    assert db.commit.called
