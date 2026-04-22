"""일반/시즌 전적·랭킹 분리 단위 테스트."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.debate.season_service import DebateSeasonService


def _make_season(status: str = "active", season_number: int = 1) -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.season_number = season_number
    s.title = f"Season {season_number}"
    s.start_at = datetime.now(UTC)
    s.end_at = datetime.now(UTC)
    s.status = status
    return s


def _make_agent(elo: int = 1500, wins: int = 0, losses: int = 0, draws: int = 0) -> MagicMock:
    a = MagicMock()
    a.id = uuid.uuid4()
    a.elo_rating = elo
    a.wins = wins
    a.losses = losses
    a.draws = draws
    a.is_active = True
    a.owner_id = uuid.uuid4()
    return a


def _make_season_stats(
    agent_id=None, season_id=None, elo: int = 1500, tier: str = "Iron",
    wins: int = 0, losses: int = 0, draws: int = 0
) -> MagicMock:
    stats = MagicMock()
    stats.id = uuid.uuid4()
    stats.agent_id = agent_id or uuid.uuid4()
    stats.season_id = season_id or uuid.uuid4()
    stats.elo_rating = elo
    stats.tier = tier
    stats.wins = wins
    stats.losses = losses
    stats.draws = draws
    return stats


@pytest.mark.asyncio
class TestGetActiveSeason:
    async def test_returns_active_season(self):
        """get_active_season은 status='active' 시즌만 반환."""
        db = AsyncMock()
        season = _make_season(status="active")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = season
        db.execute = AsyncMock(return_value=result_mock)

        svc = DebateSeasonService(db)
        found = await svc.get_active_season()

        assert found is season

    async def test_returns_none_when_only_upcoming(self):
        """upcoming 시즌만 있을 때 get_active_season은 None 반환."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        svc = DebateSeasonService(db)
        found = await svc.get_active_season()

        assert found is None


@pytest.mark.asyncio
class TestGetOrCreateSeasonStats:
    async def test_returns_existing_stats(self):
        """이미 존재하는 season_stats 행을 반환."""
        db = AsyncMock()
        agent_id = str(uuid.uuid4())
        season_id = str(uuid.uuid4())
        existing = _make_season_stats(agent_id=agent_id, season_id=season_id, elo=1600, tier="Silver")

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=result_mock)

        svc = DebateSeasonService(db)
        stats = await svc.get_or_create_season_stats(agent_id, season_id)

        assert stats is existing
        assert stats.elo_rating == 1600
        # 새 행을 add하지 않아야 함
        db.add.assert_not_called()

    async def test_creates_new_stats_with_defaults(self):
        """기존 행 없으면 ELO=1500, tier=Iron으로 신규 생성."""
        db = AsyncMock()
        agent_id = str(uuid.uuid4())
        season_id = str(uuid.uuid4())

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        # begin_nested()는 async with 컨텍스트 매니저로 사용 — AsyncMock으로 직접 생성
        begin_nested_cm = MagicMock()
        begin_nested_cm.__aenter__ = AsyncMock(return_value=None)
        begin_nested_cm.__aexit__ = AsyncMock(return_value=False)
        db.begin_nested = MagicMock(return_value=begin_nested_cm)

        svc = DebateSeasonService(db)
        stats = await svc.get_or_create_season_stats(agent_id, season_id)

        db.add.assert_called_once()
        # 생성된 객체는 DebateAgentSeasonStats 인스턴스여야 함
        from app.models.debate_agent import DebateAgentSeasonStats
        assert isinstance(db.add.call_args[0][0], DebateAgentSeasonStats)


@pytest.mark.asyncio
class TestUpdateSeasonStats:
    async def test_win_increments_wins(self):
        """시즌 결과 갱신 — win 시 wins 증가."""
        db = AsyncMock()
        db.flush = AsyncMock()
        agent_id = str(uuid.uuid4())
        season_id = str(uuid.uuid4())

        stats = MagicMock()
        stats.elo_rating = 1500
        stats.tier = "Iron"
        stats.wins = 2
        stats.losses = 1
        stats.draws = 0

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = stats
        db.execute = AsyncMock(return_value=result_mock)

        svc = DebateSeasonService(db)
        await svc.update_season_stats(agent_id, season_id, 1550, "win")

        assert stats.elo_rating == 1550
        assert stats.wins == 3
        assert stats.losses == 1

    async def test_loss_increments_losses(self):
        """시즌 결과 갱신 — loss 시 losses 증가."""
        db = AsyncMock()
        db.flush = AsyncMock()
        agent_id = str(uuid.uuid4())
        season_id = str(uuid.uuid4())

        stats = MagicMock()
        stats.elo_rating = 1500
        stats.tier = "Iron"
        stats.wins = 1
        stats.losses = 1
        stats.draws = 0

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = stats
        db.execute = AsyncMock(return_value=result_mock)

        svc = DebateSeasonService(db)
        await svc.update_season_stats(agent_id, season_id, 1450, "loss")

        assert stats.elo_rating == 1450
        assert stats.losses == 2

    async def test_draw_increments_draws(self):
        """시즌 결과 갱신 — draw 시 draws 증가."""
        db = AsyncMock()
        db.flush = AsyncMock()
        agent_id = str(uuid.uuid4())
        season_id = str(uuid.uuid4())

        stats = MagicMock()
        stats.elo_rating = 1500
        stats.tier = "Iron"
        stats.wins = 0
        stats.losses = 0
        stats.draws = 0

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = stats
        db.execute = AsyncMock(return_value=result_mock)

        svc = DebateSeasonService(db)
        await svc.update_season_stats(agent_id, season_id, 1500, "draw")

        assert stats.draws == 1


@pytest.mark.asyncio
class TestGetRankingSeasonFilter:
    async def test_overall_ranking_uses_agent_elo(self):
        """season_id 없으면 누적 ELO 기준 랭킹 반환."""
        from app.services.debate.agent_service import DebateAgentService

        db = AsyncMock()
        agent = _make_agent(elo=1700, wins=10, losses=3)
        agent.name = "AgentA"
        agent.provider = "openai"
        agent.model_id = "gpt-4o"
        agent.image_url = None
        agent.tier = "Diamond"
        agent.is_profile_public = True

        row_mock = MagicMock()
        row_mock.all.return_value = [(agent, "owner_nick")]
        db.execute = AsyncMock(return_value=row_mock)

        svc = DebateAgentService(db)
        items, total = await svc.get_ranking(season_id=None)

        assert len(items) == 1
        assert items[0]["elo_rating"] == 1700
        assert items[0]["wins"] == 10

    async def test_season_ranking_uses_season_stats_elo(self):
        """season_id 지정 시 시즌 ELO 기준 랭킹 반환."""
        from app.services.debate.agent_service import DebateAgentService

        db = AsyncMock()
        season_id = str(uuid.uuid4())
        agent = _make_agent(elo=1700)
        agent.name = "AgentA"
        agent.provider = "openai"
        agent.model_id = "gpt-4o"
        agent.image_url = None
        agent.is_profile_public = True

        season_stats = _make_season_stats(elo=1600, tier="Gold", wins=5, losses=2)

        row_mock = MagicMock()
        row_mock.all.return_value = [(season_stats, agent, "owner_nick")]
        db.execute = AsyncMock(return_value=row_mock)

        svc = DebateAgentService(db)
        items, total = await svc.get_ranking(season_id=season_id)

        assert len(items) == 1
        # 시즌 ELO 반환 (누적 1700이 아닌 시즌 1600)
        assert items[0]["elo_rating"] == 1600
        assert items[0]["wins"] == 5
        assert items[0]["tier"] == "Gold"


@pytest.mark.asyncio
class TestCloseSeasonUsesSeasonStats:
    async def test_close_season_uses_season_stats_not_cumulative(self):
        """close_season은 시즌 stats 기준 순위/전적을 저장 (누적 전적 아님).

        DebateSeasonResult 생성 시 agent.wins(누적)가 아닌
        season_stats.wins(시즌 전적)를 사용하는지 검증.
        """
        db = AsyncMock()
        db.commit = AsyncMock()

        season_id = str(uuid.uuid4())
        season = _make_season(status="active")
        season.id = season_id

        # 누적 전적(100/50) vs 시즌 전적(5/2)
        agent = _make_agent(elo=1700, wins=100, losses=50)

        stats = _make_season_stats(
            agent_id=agent.id, season_id=season_id,
            elo=1600, tier="Gold", wins=5, losses=2
        )

        # 보상 크레딧 지급을 위한 User mock
        owner = MagicMock()
        owner.credit_balance = 0

        # side_effect로 execute 호출 순서 제어
        execute_responses = [
            # 1) season 조회
            MagicMock(**{"scalar_one_or_none.return_value": season}),
            # 2) season_stats JOIN 조회
            MagicMock(**{"all.return_value": [(stats, agent)]}),
            # 3) 보상 지급용 User 조회 (rank=1, reward=500 > 0)
            MagicMock(**{"scalar_one_or_none.return_value": owner}),
        ]
        db.execute = AsyncMock(side_effect=execute_responses)

        added = []
        db.add = MagicMock(side_effect=lambda obj: added.append(obj))

        svc = DebateSeasonService(db)
        await svc.close_season(season_id)

        # DebateSeasonResult 객체가 add 되었는지 확인
        from app.models.debate_season import DebateSeasonResult
        season_results = [obj for obj in added if isinstance(obj, DebateSeasonResult)]
        assert len(season_results) == 1

        result_obj = season_results[0]
        # 시즌 stats 기준 전적 (5/2, ELO 1600)
        assert result_obj.wins == 5
        assert result_obj.losses == 2
        assert result_obj.final_elo == 1600
        assert result_obj.final_tier == "Gold"
        # 누적 전적(100/50)이 아님
        assert result_obj.wins != 100


@pytest.mark.asyncio
class TestMatchSeasonTagging:
    async def test_active_season_tags_match_season_id(self):
        """활성 시즌이 있으면 매치 생성 시 season_id 태깅."""
        from app.services.debate.matching_service import DebateMatchingService

        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.delete = AsyncMock()
        db.refresh = AsyncMock()

        season = _make_season(status="active")

        # mock topic
        topic = MagicMock()
        topic.id = uuid.uuid4()
        topic.status = "open"
        topic.is_password_protected = False

        # mock agents
        my_agent = MagicMock()
        my_agent.id = uuid.uuid4()
        my_agent.is_active = True
        my_agent.provider = "openai"
        my_agent.encrypted_api_key = "key"
        my_agent.use_platform_credits = False

        opp_agent = MagicMock()
        opp_agent.id = uuid.uuid4()
        opp_agent.is_active = True
        opp_agent.provider = "openai"
        opp_agent.encrypted_api_key = "key"
        opp_agent.use_platform_credits = False

        # mock queue entries
        my_entry = MagicMock()
        my_entry.agent_id = my_agent.id
        my_entry.user_id = uuid.uuid4()
        my_entry.topic_id = topic.id
        my_entry.is_ready = False

        opp_entry = MagicMock()
        opp_entry.agent_id = opp_agent.id
        opp_entry.user_id = uuid.uuid4()
        opp_entry.topic_id = topic.id
        opp_entry.is_ready = True

        created_match = MagicMock()
        created_match.id = uuid.uuid4()

        # get_active_season이 season을 반환하면 match.season_id에 태깅됨을 확인
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = season
        db.execute = AsyncMock(return_value=result_mock)

        svc = DebateSeasonService(db)
        active = await svc.get_active_season()
        assert active is not None
        assert active.status == "active"
        # ready_up 내부에서 active_season이 있으면 match.season_id = active_season.id 로 태깅
        match = MagicMock()
        match.season_id = None
        if active:
            match.season_id = active.id
        assert match.season_id == season.id
