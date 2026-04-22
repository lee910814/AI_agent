"""알림 서비스 단위 테스트."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_service import NotificationService


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _make_db():
    """기본 AsyncSession mock."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.add_all = MagicMock()
    return db


def _make_notification(user_id=None, is_read=False):
    """테스트용 UserNotification 목 객체."""
    n = MagicMock()
    n.id = uuid.uuid4()
    n.user_id = user_id or uuid.uuid4()
    n.type = "match_started"
    n.title = "매치 시작"
    n.body = "A vs B"
    n.link = "/debate/matches/123"
    n.is_read = is_read
    return n


def _scalar_result(value):
    """db.execute()가 scalar_one_or_none()을 반환하는 result mock."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=value)
    return mock_result


def _scalars_result(values):
    """db.execute()가 scalars().all()을 반환하는 result mock."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = values
    return mock_result


def _counts_result(total: int, unread: int):
    """db.execute()가 .one().total / .one().unread를 반환하는 result mock."""
    row = MagicMock()
    row.total = total
    row.unread = unread
    mock_result = MagicMock()
    mock_result.one.return_value = row
    return mock_result


# ──────────────────────────────────────────────
# create()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestCreate:
    async def test_create_notification(self):
        """알림 1건 생성 — add/flush 호출 후 UserNotification 객체를 반환한다."""
        db = _make_db()
        svc = NotificationService(db)

        user_id = uuid.uuid4()
        result = await svc.create(
            user_id=user_id,
            type="match_started",
            title="매치 시작",
            body="A vs B",
            link="/debate/matches/1",
        )

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result.user_id == user_id
        assert result.type == "match_started"
        assert result.title == "매치 시작"


# ──────────────────────────────────────────────
# create_bulk()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestCreateBulk:
    async def test_create_bulk(self):
        """알림 N건 일괄 생성 — add_all/flush 호출 후 예외 없이 완료된다."""
        db = _make_db()
        svc = NotificationService(db)

        notifications = [
            {"user_id": uuid.uuid4(), "type": "match_started", "title": "매치 시작", "body": "A vs B", "link": "/x"},
            {"user_id": uuid.uuid4(), "type": "match_started", "title": "매치 시작", "body": "A vs B", "link": "/x"},
        ]
        await svc.create_bulk(notifications)

        db.add_all.assert_called_once()
        db.flush.assert_called_once()

    async def test_create_bulk_empty(self):
        """빈 리스트 전달 시 예외 없이 즉시 반환한다."""
        db = _make_db()
        svc = NotificationService(db)

        await svc.create_bulk([])

        db.add_all.assert_not_called()
        db.flush.assert_not_called()

    async def test_create_bulk_swallows_exception_on_db_error(self):
        """flush 실패 시 예외를 전파하지 않고 rollback만 호출한다."""
        db = _make_db()
        db.flush = AsyncMock(side_effect=Exception("DB error"))
        svc = NotificationService(db)

        # 예외가 전파되지 않아야 한다
        await svc.create_bulk([
            {"user_id": uuid.uuid4(), "type": "t", "title": "t", "body": None, "link": None}
        ])

        db.rollback.assert_called_once()


# ──────────────────────────────────────────────
# get_list()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetList:
    async def test_get_list(self):
        """알림 목록과 전체 수를 페이지네이션으로 반환한다."""
        user_id = uuid.uuid4()
        notifications = [_make_notification(user_id=user_id) for _ in range(3)]

        db = _make_db()
        # execute 1st call: 집계 쿼리, 2nd call: 목록 쿼리
        db.execute = AsyncMock(side_effect=[
            _counts_result(total=3, unread=1),
            _scalars_result(notifications),
        ])

        svc = NotificationService(db)
        items, total, unread_count = await svc.get_list(user_id, offset=0, limit=20)

        assert total == 3
        assert unread_count == 1
        assert len(items) == 3

    async def test_get_list_unread_only(self):
        """unread_only=True 시 읽지 않은 알림만 조회한다."""
        user_id = uuid.uuid4()
        unread = [_make_notification(user_id=user_id, is_read=False)]

        db = _make_db()
        db.execute = AsyncMock(side_effect=[
            _counts_result(total=1, unread=1),
            _scalars_result(unread),
        ])

        svc = NotificationService(db)
        items, total, unread_count = await svc.get_list(user_id, offset=0, limit=20, unread_only=True)

        assert total == 1
        assert all(not item.is_read for item in items)

    async def test_get_list_empty_returns_zero(self):
        """알림이 없을 때 빈 목록과 0을 반환한다."""
        db = _make_db()
        db.execute = AsyncMock(side_effect=[
            _counts_result(total=0, unread=0),
            _scalars_result([]),
        ])

        svc = NotificationService(db)
        items, total, unread_count = await svc.get_list(uuid.uuid4(), offset=0, limit=20)

        assert total == 0
        assert unread_count == 0
        assert items == []


# ──────────────────────────────────────────────
# get_unread_count()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetUnreadCount:
    async def test_get_unread_count(self):
        """미읽기 알림 수를 정확히 반환한다."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=5)
        svc = NotificationService(db)

        count = await svc.get_unread_count(uuid.uuid4())

        assert count == 5

    async def test_get_unread_count_none_returns_zero(self):
        """scalar가 None을 반환해도 0으로 변환된다."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=None)
        svc = NotificationService(db)

        count = await svc.get_unread_count(uuid.uuid4())

        assert count == 0


# ──────────────────────────────────────────────
# mark_read()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestMarkRead:
    async def test_mark_read(self):
        """단건 읽음 처리 — is_read가 True로 변경된다."""
        user_id = uuid.uuid4()
        notification = _make_notification(user_id=user_id, is_read=False)

        db = _make_db()
        db.execute = AsyncMock(return_value=_scalar_result(notification))

        svc = NotificationService(db)
        await svc.mark_read(notification.id, user_id)

        assert notification.is_read is True

    async def test_mark_read_not_owner_raises_permission_error(self):
        """타인의 알림 읽음 처리 → PermissionError('not_owner')."""
        owner_id = uuid.uuid4()
        other_id = uuid.uuid4()
        notification = _make_notification(user_id=owner_id, is_read=False)

        db = _make_db()
        db.execute = AsyncMock(return_value=_scalar_result(notification))

        svc = NotificationService(db)
        with pytest.raises(PermissionError, match="not_owner"):
            await svc.mark_read(notification.id, other_id)

    async def test_mark_read_not_found_raises_value_error(self):
        """존재하지 않는 알림 읽음 처리 → ValueError('notification_not_found')."""
        db = _make_db()
        db.execute = AsyncMock(return_value=_scalar_result(None))

        svc = NotificationService(db)
        with pytest.raises(ValueError, match="notification_not_found"):
            await svc.mark_read(uuid.uuid4(), uuid.uuid4())


# ──────────────────────────────────────────────
# mark_all_read()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestMarkAllRead:
    async def test_mark_all_read(self):
        """전체 읽음 처리 — execute가 호출된다."""
        db = _make_db()
        mock_result = MagicMock()
        mock_result.rowcount = 4
        db.execute = AsyncMock(return_value=mock_result)

        svc = NotificationService(db)
        count = await svc.mark_all_read(uuid.uuid4())

        db.execute.assert_called_once()
        assert count == 4

    async def test_mark_all_read_returns_count(self):
        """읽음 처리된 건수를 정확히 반환한다."""
        db = _make_db()
        mock_result = MagicMock()
        mock_result.rowcount = 7
        db.execute = AsyncMock(return_value=mock_result)

        svc = NotificationService(db)
        count = await svc.mark_all_read(uuid.uuid4())

        assert count == 7

    async def test_mark_all_read_no_unread_returns_zero(self):
        """미읽기 알림이 없으면 0을 반환한다."""
        db = _make_db()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        db.execute = AsyncMock(return_value=mock_result)

        svc = NotificationService(db)
        count = await svc.mark_all_read(uuid.uuid4())

        assert count == 0
