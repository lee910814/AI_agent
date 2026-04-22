"""run_turns_1v1 단위 테스트. 순차/병렬 모드, 리뷰 활성/비활성."""

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.debate.debate_formats import TurnLoopResult
from app.services.debate.format_1v1 import run_turns_1v1
from app.services.debate.forfeit import ForfeitError


def _make_agent(provider: str = "openai") -> MagicMock:
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.owner_id = uuid.uuid4()
    agent.provider = provider
    agent.model_id = "gpt-4o-mini"
    agent.name = "테스트 에이전트"
    agent.elo_rating = 1500
    return agent


def _make_match() -> MagicMock:
    match = MagicMock()
    match.id = uuid.uuid4()
    match.is_test = False
    match.season_id = None
    match.tournament_id = None
    return match


def _make_topic(max_turns: int = 2) -> MagicMock:
    topic = MagicMock()
    topic.title = "AI는 위험한가"
    topic.description = "AI의 위험성에 대한 토론"
    topic.max_turns = max_turns
    topic.turn_token_limit = 500
    topic.tools_enabled = False
    return topic


def _make_turn_log(turn_number: int = 1, speaker: str = "agent_a", claim: str = "테스트 주장") -> MagicMock:
    turn = MagicMock()
    turn.id = uuid.uuid4()
    turn.turn_number = turn_number
    turn.speaker = speaker
    turn.claim = claim
    turn.evidence = None
    turn.action = "argue"
    turn.penalties = None
    turn.penalty_total = 0
    turn.is_blocked = False
    turn.review_result = None
    turn.response_time_ms = 100
    turn.input_tokens = 50
    turn.output_tokens = 100
    return turn


def _make_review_result() -> dict:
    return {
        "logic_score": 8,
        "violations": [],
        "penalties": {},
        "feedback": "논리적인 주장입니다.",
        "block": False,
        "blocked_claim": "",
        "model_id": "gpt-5-nano",
        "input_tokens": 30,
        "output_tokens": 20,
        "skipped": False,
    }


class TestRunTurns1v1Sequential:
    """run_turns_1v1 순차(parallel=False) 모드 테스트."""

    @pytest.mark.asyncio
    async def test_run_turns_1v1_순차모드_정상완료(self):
        """parallel=False, 2턴 기준 정상 완료 시 TurnLoopResult를 반환한다."""
        db = AsyncMock()
        agent_a = _make_agent()
        agent_b = _make_agent()
        match = _make_match()
        topic = _make_topic(max_turns=2)

        turn_a_t1 = _make_turn_log(turn_number=1, speaker="agent_a", claim="A-주장-1")
        turn_b_t1 = _make_turn_log(turn_number=1, speaker="agent_b", claim="B-주장-1")
        turn_a_t2 = _make_turn_log(turn_number=2, speaker="agent_a", claim="A-주장-2")
        turn_b_t2 = _make_turn_log(turn_number=2, speaker="agent_b", claim="B-주장-2")

        executor_mock = MagicMock()
        # 순서대로 A/B 쌍 반환: turn1-A, turn1-B, turn2-A, turn2-B
        executor_mock.execute_with_retry = AsyncMock(
            side_effect=[turn_a_t1, turn_b_t1, turn_a_t2, turn_b_t2]
        )

        orchestrator_mock = MagicMock()
        review = _make_review_result()
        orchestrator_mock.review_turn = AsyncMock(return_value=review)

        with (
            patch("app.services.debate.format_1v1._log_orchestrator_usage", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_turn_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_review_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1.settings") as mock_settings,
        ):
            mock_settings.debate_turn_review_enabled = False
            mock_settings.debate_turn_delay_seconds = 0

            result = await run_turns_1v1(
                executor=executor_mock,
                orchestrator=orchestrator_mock,
                db=db,
                match=match,
                topic=topic,
                agent_a=agent_a,
                agent_b=agent_b,
                version_a=None,
                version_b=None,
                api_key_a="key-a",
                api_key_b="key-b",
                model_cache={},
                usage_batch=[],
                parallel=False,
            )

        assert isinstance(result, TurnLoopResult)
        # 2턴이므로 각 에이전트의 claims가 2개씩 쌓여야 함
        assert len(result.claims_a) == 2
        assert len(result.claims_b) == 2
        assert result.claims_a[0] == "A-주장-1"
        assert result.claims_b[0] == "B-주장-1"
        assert result.total_penalty_a == 0
        assert result.total_penalty_b == 0

    @pytest.mark.asyncio
    async def test_run_turns_1v1_순차모드_리뷰활성_벌점누적(self):
        """순차 모드에서 debate_turn_review_enabled=True이면 리뷰 결과의 벌점이 누적된다."""
        db = AsyncMock()
        agent_a = _make_agent()
        agent_b = _make_agent()
        match = _make_match()
        topic = _make_topic(max_turns=1)

        turn_a = _make_turn_log(turn_number=1, speaker="agent_a", claim="A-주장")
        turn_b = _make_turn_log(turn_number=1, speaker="agent_b", claim="B-주장")

        executor_mock = MagicMock()
        executor_mock.execute_with_retry = AsyncMock(side_effect=[turn_a, turn_b])

        review_with_penalty = _make_review_result()
        review_with_penalty["penalties"] = {"off_topic": 5}

        orchestrator_mock = MagicMock()
        orchestrator_mock.review_turn = AsyncMock(return_value=review_with_penalty)

        with (
            patch("app.services.debate.format_1v1._log_orchestrator_usage", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_turn_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_review_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1.settings") as mock_settings,
        ):
            mock_settings.debate_turn_review_enabled = True
            mock_settings.debate_turn_delay_seconds = 0
            mock_settings.debate_forfeit_on_severe_streak = 0

            result = await run_turns_1v1(
                executor=executor_mock,
                orchestrator=orchestrator_mock,
                db=db,
                match=match,
                topic=topic,
                agent_a=agent_a,
                agent_b=agent_b,
                version_a=None,
                version_b=None,
                api_key_a="key-a",
                api_key_b="key-b",
                model_cache={},
                usage_batch=[],
                parallel=False,
            )

        assert isinstance(result, TurnLoopResult)
        # 리뷰 활성 시 벌점이 total_penalty에 누적돼야 함
        assert result.total_penalty_a == 5
        assert result.total_penalty_b == 5

    @pytest.mark.asyncio
    async def test_run_turns_1v1_순차모드_에이전트A실패_ForfeitError발생(self):
        """에이전트A의 execute_with_retry가 None 반환 시 ForfeitError가 발생한다."""
        db = AsyncMock()
        agent_a = _make_agent()
        agent_b = _make_agent()
        match = _make_match()
        topic = _make_topic(max_turns=2)

        executor_mock = MagicMock()
        # A 턴 첫 번째 시도에서 None 반환 (재시도 소진)
        executor_mock.execute_with_retry = AsyncMock(return_value=None)

        orchestrator_mock = MagicMock()

        with (
            patch("app.services.debate.format_1v1._log_orchestrator_usage", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_turn_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_review_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1.settings") as mock_settings,
        ):
            mock_settings.debate_turn_review_enabled = False
            mock_settings.debate_turn_delay_seconds = 0

            with pytest.raises(ForfeitError) as exc_info:
                await run_turns_1v1(
                    executor=executor_mock,
                    orchestrator=orchestrator_mock,
                    db=db,
                    match=match,
                    topic=topic,
                    agent_a=agent_a,
                    agent_b=agent_b,
                    version_a=None,
                    version_b=None,
                    api_key_a="key-a",
                    api_key_b="key-b",
                    model_cache={},
                    usage_batch=[],
                    parallel=False,
                )

        assert exc_info.value.forfeited_speaker == "agent_a"


class TestRunTurns1v1Parallel:
    """run_turns_1v1 병렬(parallel=True) 모드 테스트."""

    @pytest.mark.asyncio
    async def test_run_turns_1v1_병렬모드_정상완료(self):
        """parallel=True, 2턴 기준 정상 완료 시 TurnLoopResult를 반환한다."""
        db = AsyncMock()
        agent_a = _make_agent()
        agent_b = _make_agent()
        match = _make_match()
        topic = _make_topic(max_turns=2)

        turn_a_t1 = _make_turn_log(turn_number=1, speaker="agent_a", claim="A-병렬-주장-1")
        turn_b_t1 = _make_turn_log(turn_number=1, speaker="agent_b", claim="B-병렬-주장-1")
        turn_a_t2 = _make_turn_log(turn_number=2, speaker="agent_a", claim="A-병렬-주장-2")
        turn_b_t2 = _make_turn_log(turn_number=2, speaker="agent_b", claim="B-병렬-주장-2")

        executor_mock = MagicMock()
        executor_mock.execute_with_retry = AsyncMock(
            side_effect=[turn_a_t1, turn_b_t1, turn_a_t2, turn_b_t2]
        )

        orchestrator_mock = MagicMock()
        orchestrator_mock.review_turn = AsyncMock(return_value=_make_review_result())
        orchestrator_mock._review_fallback = MagicMock(return_value=_make_review_result())

        with (
            patch("app.services.debate.format_1v1._log_orchestrator_usage", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_turn_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_review_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1.settings") as mock_settings,
        ):
            mock_settings.debate_turn_review_enabled = False
            mock_settings.debate_turn_delay_seconds = 0

            result = await run_turns_1v1(
                executor=executor_mock,
                orchestrator=orchestrator_mock,
                db=db,
                match=match,
                topic=topic,
                agent_a=agent_a,
                agent_b=agent_b,
                version_a=None,
                version_b=None,
                api_key_a="key-a",
                api_key_b="key-b",
                model_cache={},
                usage_batch=[],
                parallel=True,
            )

        assert isinstance(result, TurnLoopResult)
        assert len(result.claims_a) == 2
        assert len(result.claims_b) == 2
        assert result.claims_a[0] == "A-병렬-주장-1"
        assert result.claims_b[0] == "B-병렬-주장-1"
        assert result.total_penalty_a == 0
        assert result.total_penalty_b == 0

    @pytest.mark.asyncio
    async def test_run_turns_1v1_병렬모드_순차대비30퍼센트이상빠름(self):
        """롤링 create_task 병렬 패턴 성능 검증.

        review_turn에 sleep(0.3) 딜레이를 주어 병렬 모드가 순차 모드 대비 ≥30% 빠른지 확인한다.
        병렬 모드에서는 A 리뷰와 B 실행이 겹쳐 리뷰 대기 시간이 숨겨진다.
        """
        REVIEW_DELAY = 0.3
        EXEC_DELAY = 0.05

        async def slow_review(**kwargs):
            await asyncio.sleep(REVIEW_DELAY)
            return _make_review_result()

        async def slow_exec(*args, **kwargs):
            await asyncio.sleep(EXEC_DELAY)
            return _make_turn_log(turn_number=kwargs.get("turn_number", 1), speaker=kwargs.get("speaker", "agent_a"))

        db = AsyncMock()
        agent_a = _make_agent()
        agent_b = _make_agent()
        match = _make_match()
        topic = _make_topic(max_turns=2)

        def make_executor():
            exc = MagicMock()
            exc.execute_with_retry = AsyncMock(side_effect=slow_exec)
            return exc

        def make_orch():
            orch = MagicMock()
            orch.review_turn = AsyncMock(side_effect=slow_review)
            orch._review_fallback = MagicMock(return_value=_make_review_result())
            return orch

        common_kwargs = dict(
            db=db,
            match=match,
            topic=topic,
            agent_a=agent_a,
            agent_b=agent_b,
            version_a=None,
            version_b=None,
            api_key_a="key-a",
            api_key_b="key-b",
            model_cache={},
            usage_batch=[],
        )

        with (
            patch("app.services.debate.format_1v1._log_orchestrator_usage", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_turn_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1._publish_review_event", new_callable=AsyncMock),
            patch("app.services.debate.format_1v1.settings") as mock_settings,
        ):
            mock_settings.debate_turn_review_enabled = True
            mock_settings.debate_turn_delay_seconds = 0
            mock_settings.debate_forfeit_on_severe_streak = 0

            t0 = time.monotonic()
            await run_turns_1v1(executor=make_executor(), orchestrator=make_orch(), parallel=True, **common_kwargs)
            parallel_elapsed = time.monotonic() - t0

            t0 = time.monotonic()
            await run_turns_1v1(executor=make_executor(), orchestrator=make_orch(), parallel=False, **common_kwargs)
            sequential_elapsed = time.monotonic() - t0

        # 병렬 모드가 순차 모드 대비 30% 이상 빠른지 검증
        assert parallel_elapsed < sequential_elapsed * 0.7, (
            f"병렬({parallel_elapsed:.2f}s) 이 순차({sequential_elapsed:.2f}s) 대비 30% 이상 빠르지 않음"
        )
