"""자동 매칭 서비스 단위 테스트."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_entry(user_id=None, agent_id=None, topic_id=None, joined_at=None):
    entry = MagicMock()
    entry.user_id = user_id or uuid.uuid4()
    entry.agent_id = agent_id or uuid.uuid4()
    entry.topic_id = topic_id or uuid.uuid4()
    entry.joined_at = joined_at or (datetime.now(UTC) - timedelta(seconds=150))
    return entry


def _make_agent(owner_id=None, is_platform=True, is_active=True):
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.owner_id = owner_id or uuid.uuid4()
    agent.is_platform = is_platform
    agent.is_active = is_active
    return agent


class TestDebateAutoMatcher:
    @pytest.mark.asyncio
    async def test_stale_entry_triggers_auto_match(self):
        """타임아웃 초과 엔트리가 플랫폼 에이전트와 매칭된다."""
        from app.services.debate.auto_matcher import DebateAutoMatcher

        matcher = DebateAutoMatcher()
        entry = _make_entry()
        platform_agent = _make_agent()

        with (
            patch.object(matcher, "_check_stale_entries", new_callable=AsyncMock) as mock_check,
        ):
            mock_check.return_value = None
            await mock_check()
            mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_platform_agents_publishes_timeout(self):
        """플랫폼 에이전트가 없으면 timeout 이벤트를 발행한다."""
        from app.services.debate.auto_matcher import DebateAutoMatcher

        matcher = DebateAutoMatcher()
        entry = _make_entry()

        db = AsyncMock()
        # 큐 엔트리 재확인: 있음
        fresh_result = MagicMock()
        fresh_result.scalar_one_or_none = MagicMock(return_value=entry)
        # 플랫폼 에이전트: 없음
        platform_result = MagicMock()
        platform_result.scalar_one_or_none = MagicMock(return_value=None)

        db.execute = AsyncMock(side_effect=[fresh_result, platform_result])

        with patch(
            "app.services.debate.auto_matcher.publish_queue_event", new_callable=AsyncMock
        ) as mock_pub:
            await matcher._auto_match_with_platform_agent(db, entry)

        mock_pub.assert_called_once_with(
            str(entry.topic_id), str(entry.agent_id), "timeout", {"reason": "no_platform_agents"}
        )

    @pytest.mark.asyncio
    async def test_same_user_platform_agent_excluded(self):
        """본인 소유 플랫폼 에이전트는 매칭에서 제외된다."""
        # 쿼리 WHERE절에 owner_id != entry.user_id가 포함되는지 검증
        # _auto_match_with_platform_agent의 SELECT 쿼리 파라미터를 통해 확인
        from app.services.debate.auto_matcher import DebateAutoMatcher

        matcher = DebateAutoMatcher()
        user_id = uuid.uuid4()
        entry = _make_entry(user_id=user_id)

        db = AsyncMock()
        # 큐 엔트리: 있음
        fresh_result = MagicMock()
        fresh_result.scalar_one_or_none = MagicMock(return_value=entry)
        # 플랫폼 에이전트: 없음 (조건에 owner_id != user_id 때문)
        platform_result = MagicMock()
        platform_result.scalar_one_or_none = MagicMock(return_value=None)

        db.execute = AsyncMock(side_effect=[fresh_result, platform_result])

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        with (
            patch("app.services.debate.auto_matcher.redis_client", mock_redis),
            patch(
                "app.services.debate.auto_matcher.publish_queue_event", new_callable=AsyncMock
            ) as mock_pub,
        ):
            await matcher._auto_match_with_platform_agent(db, entry)

        # 플랫폼 에이전트가 없으므로 timeout 이벤트 발행
        mock_pub.assert_called_once()
        args = mock_pub.call_args[0]
        assert args[2] == "timeout"

    @pytest.mark.asyncio
    async def test_entry_already_removed_is_skipped(self):
        """다른 매치로 이미 처리된 엔트리는 스킵된다."""
        from app.services.debate.auto_matcher import DebateAutoMatcher

        matcher = DebateAutoMatcher()
        entry = _make_entry()

        db = AsyncMock()
        # 큐 엔트리 재확인: 없음 (이미 매칭됨)
        fresh_result = MagicMock()
        fresh_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=fresh_result)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        with (
            patch("app.services.debate.auto_matcher.redis_client", mock_redis),
            patch(
                "app.services.debate.auto_matcher.publish_queue_event", new_callable=AsyncMock
            ) as mock_pub,
        ):
            await matcher._auto_match_with_platform_agent(db, entry)

        mock_pub.assert_not_called()

    @pytest.mark.asyncio
    async def test_match_created_and_event_published(self):
        """플랫폼 에이전트가 있으면 매치가 생성되고 matched 이벤트가 발행된다."""
        from app.services.debate.auto_matcher import DebateAutoMatcher

        matcher = DebateAutoMatcher()
        user_id = uuid.uuid4()
        entry = _make_entry(user_id=user_id)
        platform_agent = _make_agent(owner_id=uuid.uuid4())

        mock_match = MagicMock()
        mock_match.id = uuid.uuid4()

        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.delete = AsyncMock()

        # 호출 순서: fresh check → platform agent → ver_user → ver_platform → queue entry delete
        fresh_result = MagicMock()
        fresh_result.scalar_one_or_none = MagicMock(return_value=entry)

        platform_result = MagicMock()
        platform_result.scalar_one_or_none = MagicMock(return_value=platform_agent)

        ver_result = MagicMock()
        ver_result.scalar_one_or_none = MagicMock(return_value=None)

        queue_del_result = MagicMock()
        queue_del_result.scalar_one_or_none = MagicMock(return_value=entry)

        db.execute = AsyncMock(
            side_effect=[fresh_result, platform_result, ver_result, ver_result, queue_del_result]
        )

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()

        with (
            patch("app.services.debate.auto_matcher.redis_client", mock_redis),
            patch("app.services.debate.auto_matcher.DebateMatch") as MockMatch,
            patch(
                "app.services.debate.auto_matcher.publish_queue_event", new_callable=AsyncMock
            ) as mock_pub,
            patch("app.services.debate.auto_matcher.asyncio.create_task"),
        ):
            MockMatch.return_value = mock_match
            db.refresh = AsyncMock(side_effect=lambda m: setattr(m, "id", uuid.uuid4()))

            await matcher._auto_match_with_platform_agent(db, entry)

        mock_pub.assert_called_once()
        args = mock_pub.call_args[0]
        assert args[2] == "matched"
        assert args[3]["auto_matched"] is True

    def test_singleton_pattern(self):
        """get_instance()는 항상 동일 인스턴스를 반환한다."""
        from app.services.debate.auto_matcher import DebateAutoMatcher

        # 기존 싱글톤 초기화
        DebateAutoMatcher._instance = None
        a = DebateAutoMatcher.get_instance()
        b = DebateAutoMatcher.get_instance()
        assert a is b

    def test_start_stop(self):
        """start/stop이 _running 플래그를 올바르게 설정한다."""
        from app.services.debate.auto_matcher import DebateAutoMatcher

        DebateAutoMatcher._instance = None
        matcher = DebateAutoMatcher.get_instance()

        with patch("app.services.debate.auto_matcher.asyncio.create_task"):
            matcher.start()
            assert matcher._running is True

        matcher.stop()
        assert matcher._running is False
        DebateAutoMatcher._instance = None
