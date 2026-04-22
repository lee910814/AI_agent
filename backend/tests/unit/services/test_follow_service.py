"""팔로우 서비스 단위 테스트."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.follow_service import FollowService


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _make_db(scalar_return=None, execute_return=None, rowcount=1):
    """AsyncSession mock 생성.

    scalar: db.scalar() 반환값 (단건 COUNT 등)
    execute: db.execute() 반환값 (result 객체)
    rowcount: execute().rowcount (DELETE 결과)
    """
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=scalar_return)
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()

    mock_result = MagicMock()
    mock_result.rowcount = rowcount
    mock_result.scalars.return_value.all.return_value = execute_return or []
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_follow(follower_id=None, target_type="agent", target_id=None):
    """테스트용 UserFollow 목 객체."""
    f = MagicMock()
    f.id = uuid.uuid4()
    f.follower_id = follower_id or uuid.uuid4()
    f.target_type = target_type
    f.target_id = target_id or uuid.uuid4()
    return f


# ──────────────────────────────────────────────
# follow()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestFollowAgent:
    async def test_follow_agent_success(self):
        """에이전트 팔로우 성공 — UserFollow 객체를 반환한다."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=1)  # 에이전트 존재
        svc = FollowService(db)

        follower_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        result = await svc.follow(follower_id, "agent", agent_id)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result.follower_id == follower_id
        assert result.target_type == "agent"
        assert result.target_id == agent_id

    async def test_follow_user_success(self):
        """사용자 팔로우 성공 — UserFollow 객체를 반환한다."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=1)  # 사용자 존재
        svc = FollowService(db)

        follower_id = uuid.uuid4()
        target_user_id = uuid.uuid4()
        result = await svc.follow(follower_id, "user", target_user_id)

        db.add.assert_called_once()
        assert result.target_type == "user"
        assert result.target_id == target_user_id

    async def test_follow_duplicate_raises_already_following(self):
        """DB IntegrityError(중복 팔로우) → ValueError('already_following') 변환."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=1)
        db.flush = AsyncMock(side_effect=IntegrityError("unique", {}, None))
        svc = FollowService(db)

        with pytest.raises(ValueError, match="already_following"):
            await svc.follow(uuid.uuid4(), "agent", uuid.uuid4())

        db.rollback.assert_called_once()

    async def test_follow_self_raises_self_follow(self):
        """자기 자신 팔로우 → ValueError('self_follow')."""
        db = _make_db()
        svc = FollowService(db)

        user_id = uuid.uuid4()
        with pytest.raises(ValueError, match="self_follow"):
            await svc.follow(user_id, "user", user_id)

    async def test_follow_nonexistent_agent_raises_target_not_found(self):
        """존재하지 않는 에이전트 팔로우 → ValueError('target_not_found')."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=0)  # 에이전트 없음
        svc = FollowService(db)

        with pytest.raises(ValueError, match="target_not_found"):
            await svc.follow(uuid.uuid4(), "agent", uuid.uuid4())

    async def test_follow_nonexistent_user_raises_target_not_found(self):
        """존재하지 않는 사용자 팔로우 → ValueError('target_not_found')."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=0)  # 사용자 없음
        svc = FollowService(db)

        follower_id = uuid.uuid4()
        other_id = uuid.uuid4()  # follower_id와 다른 값
        with pytest.raises(ValueError, match="target_not_found"):
            await svc.follow(follower_id, "user", other_id)

    async def test_follow_invalid_target_type_raises_value_error(self):
        """지원하지 않는 target_type → ValueError('invalid_target_type')."""
        db = _make_db()
        svc = FollowService(db)

        with pytest.raises(ValueError, match="invalid_target_type"):
            await svc.follow(uuid.uuid4(), "topic", uuid.uuid4())


# ──────────────────────────────────────────────
# unfollow()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestUnfollow:
    async def test_unfollow_success(self):
        """팔로우 관계 삭제 성공 — 예외 없이 완료된다."""
        db = _make_db(rowcount=1)
        svc = FollowService(db)

        # 예외가 발생하지 않으면 성공
        await svc.unfollow(uuid.uuid4(), "agent", uuid.uuid4())
        db.execute.assert_called_once()

    async def test_unfollow_nonexistent_raises_not_following(self):
        """존재하지 않는 팔로우 관계 삭제 → ValueError('not_following')."""
        db = _make_db(rowcount=0)
        svc = FollowService(db)

        with pytest.raises(ValueError, match="not_following"):
            await svc.unfollow(uuid.uuid4(), "agent", uuid.uuid4())


# ──────────────────────────────────────────────
# get_following()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetFollowing:
    async def test_get_following_all(self):
        """target_type 필터 없이 전체 팔로우 목록과 총 수를 반환한다."""
        follower_id = uuid.uuid4()
        follows = [_make_follow(follower_id=follower_id, target_type="agent"),
                   _make_follow(follower_id=follower_id, target_type="user")]

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=2)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = follows
        db.execute = AsyncMock(return_value=mock_result)

        svc = FollowService(db)
        items, total = await svc.get_following(follower_id, None, offset=0, limit=20)

        assert total == 2
        assert len(items) == 2

    async def test_get_following_filter_agent(self):
        """target_type='agent' 필터 시 에이전트 팔로우만 반환한다."""
        follower_id = uuid.uuid4()
        follows = [_make_follow(follower_id=follower_id, target_type="agent")]

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = follows
        db.execute = AsyncMock(return_value=mock_result)

        svc = FollowService(db)
        items, total = await svc.get_following(follower_id, "agent", offset=0, limit=20)

        assert total == 1
        assert items[0].target_type == "agent"

    async def test_get_following_filter_user(self):
        """target_type='user' 필터 시 사용자 팔로우만 반환한다."""
        follower_id = uuid.uuid4()
        follows = [_make_follow(follower_id=follower_id, target_type="user")]

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = follows
        db.execute = AsyncMock(return_value=mock_result)

        svc = FollowService(db)
        items, total = await svc.get_following(follower_id, "user", offset=0, limit=20)

        assert total == 1
        assert items[0].target_type == "user"

    async def test_get_following_empty_returns_zero(self):
        """팔로우가 없을 때 빈 목록과 0을 반환한다."""
        db = AsyncMock()
        db.scalar = AsyncMock(return_value=None)  # scalar가 None 반환 → or 0

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        svc = FollowService(db)
        items, total = await svc.get_following(uuid.uuid4(), None, offset=0, limit=20)

        assert total == 0
        assert items == []


# ──────────────────────────────────────────────
# get_follower_count()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetFollowerCount:
    async def test_get_follower_count(self):
        """팔로워가 있을 때 정확한 수를 반환한다."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=7)
        svc = FollowService(db)

        count = await svc.get_follower_count("agent", uuid.uuid4())

        assert count == 7

    async def test_get_follower_count_zero(self):
        """팔로워가 없을 때 0을 반환한다 (None → 0 변환 포함)."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=None)
        svc = FollowService(db)

        count = await svc.get_follower_count("agent", uuid.uuid4())

        assert count == 0


# ──────────────────────────────────────────────
# is_following()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestIsFollowing:
    async def test_is_following_true(self):
        """팔로우 중이면 True를 반환한다."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=1)
        svc = FollowService(db)

        result = await svc.is_following(uuid.uuid4(), "agent", uuid.uuid4())

        assert result is True

    async def test_is_following_false(self):
        """팔로우하지 않았으면 False를 반환한다."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=0)
        svc = FollowService(db)

        result = await svc.is_following(uuid.uuid4(), "agent", uuid.uuid4())

        assert result is False

    async def test_is_following_none_scalar_returns_false(self):
        """DB scalar가 None을 반환해도 False로 처리된다."""
        db = _make_db()
        db.scalar = AsyncMock(return_value=None)
        svc = FollowService(db)

        result = await svc.is_following(uuid.uuid4(), "user", uuid.uuid4())

        assert result is False


# ──────────────────────────────────────────────
# get_follower_user_ids()
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetFollowerUserIds:
    async def test_get_follower_user_ids(self):
        """팔로워 user_id 목록을 반환한다."""
        ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ids
        db.execute = AsyncMock(return_value=mock_result)

        svc = FollowService(db)
        result = await svc.get_follower_user_ids("agent", uuid.uuid4())

        assert result == ids
        assert len(result) == 3

    async def test_get_follower_user_ids_empty(self):
        """팔로워가 없으면 빈 리스트를 반환한다."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        svc = FollowService(db)
        result = await svc.get_follower_user_ids("agent", uuid.uuid4())

        assert result == []
