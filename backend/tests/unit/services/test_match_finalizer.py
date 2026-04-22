"""MatchFinalizer 단위 테스트. ELO 갱신, 시즌, 승급전, 토너먼트, 요약."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.debate.finalizer import MatchFinalizer


# finalizer.py 내 지역 import 경로 상수화
_AGENT_SVC = "app.services.debate.agent_service.DebateAgentService"
_PROMO_SVC = "app.services.debate.promotion_service.DebatePromotionService"
_SEASON_SVC = "app.services.debate.season_service.DebateSeasonService"
_MATCH_SVC = "app.services.debate.match_service.DebateMatchService"
_GEN_SUMMARY = "app.services.debate.match_service.generate_summary_task"
_LOG_USAGE = "app.services.debate.debate_formats._log_orchestrator_usage"
_PUBLISH = "app.services.debate.finalizer.publish_event"
_CALC_ELO = "app.services.debate.finalizer.calculate_elo"
_SETTINGS = "app.services.debate.finalizer.settings"
_TOURNAMENT_SVC = "app.services.debate.tournament_service.DebateTournamentService"


def _make_agent(elo: float = 1500.0) -> MagicMock:
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.owner_id = uuid.uuid4()
    agent.tier = "silver"
    agent.elo_rating = elo
    agent.name = "테스트 에이전트"
    return agent


def _make_match(
    is_test: bool = False,
    season_id=None,
    tournament_id=None,
) -> MagicMock:
    match = MagicMock()
    match.id = uuid.uuid4()
    match.agent_a_id = uuid.uuid4()
    match.agent_b_id = uuid.uuid4()
    match.agent_a_version_id = None
    match.agent_b_version_id = None
    match.is_test = is_test
    match.season_id = season_id
    match.tournament_id = tournament_id
    match.winner_id = None
    return match


def _make_judgment(winner_id=None, score_a: int = 70, score_b: int = 30) -> dict:
    return {
        "winner_id": winner_id,
        "score_a": score_a,
        "score_b": score_b,
        "scorecard": {"criteria": []},
        "model_id": "gpt-4.1",
        "input_tokens": 200,
        "output_tokens": 100,
    }


class TestMatchFinalizerFinalize:
    """MatchFinalizer.finalize() 핵심 경로 테스트."""

    @pytest.mark.asyncio
    async def test_finalize_1v1정상_ELO갱신_커밋(self):
        """정상 1v1 매치 완료 시 ELO가 갱신되고 DB 커밋이 호출된다."""
        db = AsyncMock()
        agent_a = _make_agent(elo=1500.0)
        agent_b = _make_agent(elo=1500.0)
        match = _make_match()
        judgment = _make_judgment(winner_id=match.agent_a_id, score_a=70, score_b=30)

        agent_service_mock = AsyncMock()
        promo_service_mock = AsyncMock()
        promo_service_mock.get_active_series.return_value = None
        match_service_mock = AsyncMock()

        with (
            patch(_AGENT_SVC, return_value=agent_service_mock),
            patch(_PROMO_SVC, return_value=promo_service_mock),
            patch(_MATCH_SVC, return_value=match_service_mock),
            patch(_LOG_USAGE, new_callable=AsyncMock),
            patch(_PUBLISH, new_callable=AsyncMock),
            patch(_CALC_ELO, return_value=(1516.0, 1484.0)),
            patch(_SETTINGS) as mock_settings,
        ):
            mock_settings.debate_summary_enabled = False

            finalizer = MatchFinalizer(db=db)
            await finalizer.finalize(
                match=match,
                judgment=judgment,
                agent_a=agent_a,
                agent_b=agent_b,
                model_cache={},
                usage_batch=[],
            )

        # ELO 갱신이 두 에이전트 모두에 대해 호출됐는지 확인
        assert agent_service_mock.update_elo.call_count == 2
        # DB 커밋이 1번 호출됐는지 확인
        db.commit.assert_called_once()
        # match 상태가 completed로 변경됐는지 확인
        assert match.status == "completed"
        assert match.winner_id == match.agent_a_id

    @pytest.mark.asyncio
    async def test_finalize_무승부_결과처리(self):
        """winner_id=None인 무승부 매치는 draw ELO 결과로 처리된다."""
        db = AsyncMock()
        agent_a = _make_agent(elo=1500.0)
        agent_b = _make_agent(elo=1500.0)
        match = _make_match()
        judgment = _make_judgment(winner_id=None, score_a=50, score_b=50)

        agent_service_mock = AsyncMock()
        promo_service_mock = AsyncMock()
        promo_service_mock.get_active_series.return_value = None
        match_service_mock = AsyncMock()

        captured_elo_result = {}

        def fake_calculate_elo(elo_a, elo_b, result, score_diff=0):
            captured_elo_result["result"] = result
            return (elo_a, elo_b)

        with (
            patch(_AGENT_SVC, return_value=agent_service_mock),
            patch(_PROMO_SVC, return_value=promo_service_mock),
            patch(_MATCH_SVC, return_value=match_service_mock),
            patch(_LOG_USAGE, new_callable=AsyncMock),
            patch(_PUBLISH, new_callable=AsyncMock),
            patch(_CALC_ELO, side_effect=fake_calculate_elo),
            patch(_SETTINGS) as mock_settings,
        ):
            mock_settings.debate_summary_enabled = False

            finalizer = MatchFinalizer(db=db)
            await finalizer.finalize(
                match=match,
                judgment=judgment,
                agent_a=agent_a,
                agent_b=agent_b,
                model_cache={},
                usage_batch=[],
            )

        # winner_id=None → elo_result="draw"로 calculate_elo 호출
        assert captured_elo_result["result"] == "draw"

    @pytest.mark.asyncio
    async def test_finalize_시즌매치_시즌ELO갱신(self):
        """match.season_id가 있을 때 시즌 ELO도 별도로 갱신된다."""
        db = AsyncMock()
        agent_a = _make_agent(elo=1500.0)
        agent_b = _make_agent(elo=1500.0)
        season_id = uuid.uuid4()
        match = _make_match(season_id=season_id)
        judgment = _make_judgment(winner_id=match.agent_a_id)

        agent_service_mock = AsyncMock()
        season_service_mock = AsyncMock()
        promo_service_mock = AsyncMock()
        match_service_mock = AsyncMock()

        fake_stats = MagicMock()
        fake_stats.elo_rating = 1500.0
        season_service_mock.get_or_create_season_stats.return_value = fake_stats
        promo_service_mock.get_active_series.return_value = None

        with (
            patch(_AGENT_SVC, return_value=agent_service_mock),
            patch(_SEASON_SVC, return_value=season_service_mock),
            patch(_PROMO_SVC, return_value=promo_service_mock),
            patch(_MATCH_SVC, return_value=match_service_mock),
            patch(_LOG_USAGE, new_callable=AsyncMock),
            patch(_PUBLISH, new_callable=AsyncMock),
            patch(_CALC_ELO, return_value=(1516.0, 1484.0)),
            patch(_SETTINGS) as mock_settings,
        ):
            mock_settings.debate_summary_enabled = False

            finalizer = MatchFinalizer(db=db)
            await finalizer.finalize(
                match=match,
                judgment=judgment,
                agent_a=agent_a,
                agent_b=agent_b,
                model_cache={},
                usage_batch=[],
            )

        # 시즌 stats 조회가 두 에이전트 모두에 대해 호출됐는지 확인
        assert season_service_mock.get_or_create_season_stats.call_count == 2
        # 시즌 ELO 갱신도 두 에이전트에 대해 호출됐는지 확인
        assert season_service_mock.update_season_stats.call_count == 2

    @pytest.mark.asyncio
    async def test_finalize_is_test_ELO갱신스킵(self):
        """is_test=True 매치에서는 ELO 갱신과 승급전 처리를 건너뛴다."""
        db = AsyncMock()
        agent_a = _make_agent(elo=1500.0)
        agent_b = _make_agent(elo=1500.0)
        match = _make_match(is_test=True)
        judgment = _make_judgment(winner_id=match.agent_a_id)

        agent_service_mock = AsyncMock()
        promo_service_mock = AsyncMock()
        match_service_mock = AsyncMock()

        with (
            patch(_AGENT_SVC, return_value=agent_service_mock),
            patch(_PROMO_SVC, return_value=promo_service_mock),
            patch(_MATCH_SVC, return_value=match_service_mock),
            patch(_LOG_USAGE, new_callable=AsyncMock),
            patch(_PUBLISH, new_callable=AsyncMock),
            patch(_CALC_ELO, return_value=(1516.0, 1484.0)),
            patch(_SETTINGS) as mock_settings,
        ):
            mock_settings.debate_summary_enabled = False

            finalizer = MatchFinalizer(db=db)
            await finalizer.finalize(
                match=match,
                judgment=judgment,
                agent_a=agent_a,
                agent_b=agent_b,
                model_cache={},
                usage_batch=[],
            )

        # is_test=True → ELO 갱신 메서드가 호출되지 않아야 함
        agent_service_mock.update_elo.assert_not_called()
        # is_test=True → 승급전 처리도 호출되지 않아야 함
        promo_service_mock.get_active_series.assert_not_called()

    @pytest.mark.asyncio
    async def test_finalize_토너먼트_advance_round호출(self):
        """match.tournament_id가 있을 때 토너먼트 advance_round()가 호출된다."""
        db = AsyncMock()
        agent_a = _make_agent(elo=1500.0)
        agent_b = _make_agent(elo=1500.0)
        tournament_id = uuid.uuid4()
        match = _make_match(tournament_id=tournament_id)
        judgment = _make_judgment(winner_id=match.agent_a_id)

        agent_service_mock = AsyncMock()
        promo_service_mock = AsyncMock()
        promo_service_mock.get_active_series.return_value = None
        match_service_mock = AsyncMock()
        tournament_service_mock = AsyncMock()

        with (
            patch(_AGENT_SVC, return_value=agent_service_mock),
            patch(_PROMO_SVC, return_value=promo_service_mock),
            patch(_MATCH_SVC, return_value=match_service_mock),
            patch(_TOURNAMENT_SVC, return_value=tournament_service_mock),
            patch(_LOG_USAGE, new_callable=AsyncMock),
            patch(_PUBLISH, new_callable=AsyncMock),
            patch(_CALC_ELO, return_value=(1516.0, 1484.0)),
            patch(_SETTINGS) as mock_settings,
        ):
            mock_settings.debate_summary_enabled = False

            finalizer = MatchFinalizer(db=db)
            await finalizer.finalize(
                match=match,
                judgment=judgment,
                agent_a=agent_a,
                agent_b=agent_b,
                model_cache={},
                usage_batch=[],
            )

        # advance_round가 올바른 tournament_id로 호출됐는지 확인
        tournament_service_mock.advance_round.assert_called_once_with(str(tournament_id))
