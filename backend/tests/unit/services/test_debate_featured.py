"""하이라이트 매치 서비스 단위 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_toggle_featured_match_not_found():
    """존재하지 않는 매치에 하이라이트 설정 시 ValueError."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    from app.services.debate.match_service import DebateMatchService

    service = DebateMatchService(db)
    with pytest.raises(ValueError, match="Match not found"):
        await service.toggle_featured("non-existent-id", True)


@pytest.mark.asyncio
async def test_toggle_featured_not_completed():
    """완료되지 않은 매치에 하이라이트 설정 시 ValueError."""
    db = AsyncMock()

    match_mock = MagicMock()
    match_mock.status = "in_progress"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = match_mock
    db.execute = AsyncMock(return_value=result_mock)

    from app.services.debate.match_service import DebateMatchService

    service = DebateMatchService(db)
    with pytest.raises(ValueError, match="완료된 매치만"):
        await service.toggle_featured("match-id", True)


@pytest.mark.asyncio
async def test_toggle_featured_success():
    """완료된 매치에 하이라이트 설정 성공."""
    db = AsyncMock()

    match_mock = MagicMock()
    match_mock.status = "completed"
    match_mock.id = "match-id"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = match_mock

    # 두 번째 execute (UPDATE)도 Mock
    db.execute = AsyncMock(return_value=result_mock)
    db.commit = AsyncMock()

    from app.services.debate.match_service import DebateMatchService

    service = DebateMatchService(db)
    result = await service.toggle_featured("match-id", True)

    assert result["ok"] is True
    assert result["is_featured"] is True


@pytest.mark.asyncio
async def test_toggle_featured_unset():
    """하이라이트 해제 성공."""
    db = AsyncMock()

    match_mock = MagicMock()
    match_mock.status = "completed"
    match_mock.id = "match-id"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = match_mock
    db.execute = AsyncMock(return_value=result_mock)
    db.commit = AsyncMock()

    from app.services.debate.match_service import DebateMatchService

    service = DebateMatchService(db)
    result = await service.toggle_featured("match-id", False)

    assert result["ok"] is True
    assert result["is_featured"] is False


@pytest.mark.asyncio
async def test_list_featured_empty():
    """하이라이트 매치가 없으면 빈 리스트."""
    db = AsyncMock()

    # 첫 번째 execute: COUNT 쿼리 → total=0
    count_mock = MagicMock()
    count_mock.scalar.return_value = 0

    # 두 번째 execute: 데이터 쿼리 → 빈 리스트
    rows_mock = MagicMock()
    rows_mock.all.return_value = []

    db.execute = AsyncMock(side_effect=[count_mock, rows_mock])

    from app.services.debate.match_service import DebateMatchService

    service = DebateMatchService(db)
    items, total = await service.list_featured(limit=5)

    assert items == []
    assert total == 0
