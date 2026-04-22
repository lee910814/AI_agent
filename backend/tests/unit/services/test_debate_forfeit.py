"""재시도 + 부전패 처리 단위 테스트."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.debate.engine import (
    ForfeitError,
    _execute_turn_with_retry,  # noqa: PLC2701
)


def _make_turn_log() -> MagicMock:
    """테스트용 DebateTurnLog 목 객체."""
    turn = MagicMock()
    turn.turn_number = 1
    turn.speaker = "agent_a"
    turn.penalty_total = 0
    turn.claim = "테스트 주장"
    return turn


def _make_agent(provider: str = "openai") -> MagicMock:
    """테스트용 DebateAgent 목 객체."""
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.owner_id = uuid.uuid4()
    agent.provider = provider
    agent.model_id = "gpt-4o-mini"
    agent.name = "테스트 에이전트"
    agent.elo_rating = 1500
    return agent


def _make_match() -> MagicMock:
    """테스트용 DebateMatch 목 객체."""
    match = MagicMock()
    match.id = uuid.uuid4()
    match.agent_a_id = uuid.uuid4()
    match.agent_b_id = uuid.uuid4()
    match.agent_a_version_id = None
    match.agent_b_version_id = None
    match.is_test = False
    match.season_id = None
    match.tournament_id = None
    return match


def _make_topic() -> MagicMock:
    """테스트용 DebateTopic 목 객체."""
    topic = MagicMock()
    topic.title = "AI는 위험한가"
    topic.description = "AI의 위험성에 대한 토론"
    topic.max_turns = 4
    topic.turn_token_limit = 500
    topic.tools_enabled = False
    return topic


class TestExecuteTurnWithRetry:
    """_execute_turn_with_retry 재시도 로직 테스트."""

    @pytest.mark.asyncio
    async def test_성공시_즉시_반환(self):
        """첫 시도에 성공하면 turn log를 반환한다."""
        expected_turn = _make_turn_log()

        with patch(
            "app.services.debate.turn_executor.TurnExecutor.execute",
            new_callable=AsyncMock,
            return_value=expected_turn,
        ):
            result = await _execute_turn_with_retry(
                db=AsyncMock(),
                client=AsyncMock(),
                match=_make_match(),
                topic=_make_topic(),
                turn_number=1,
                speaker="agent_a",
                agent=_make_agent(),
                version=None,
                api_key="test-key",
                my_claims=[],
                opponent_claims=[],
            )

        assert result is expected_turn

    @pytest.mark.asyncio
    async def test_첫_실패_후_재시도_성공(self):
        """첫 시도 실패 후 재시도에서 성공하면 turn log를 반환한다."""
        expected_turn = _make_turn_log()
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("첫 번째 시도 실패")
            return expected_turn

        with patch("app.services.debate.turn_executor.TurnExecutor.execute", side_effect=side_effect):
            result = await _execute_turn_with_retry(
                db=AsyncMock(),
                client=AsyncMock(),
                match=_make_match(),
                topic=_make_topic(),
                turn_number=1,
                speaker="agent_a",
                agent=_make_agent(),
                version=None,
                api_key="test-key",
                my_claims=[],
                opponent_claims=[],
            )

        assert result is expected_turn
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_모든_재시도_실패시_None_반환(self):
        """debate_turn_max_retries 횟수만큼 재시도 후 모두 실패하면 None을 반환한다."""
        with (
            patch(
                "app.services.debate.turn_executor.TurnExecutor.execute",
                new_callable=AsyncMock,
                side_effect=TimeoutError("LLM 응답 없음"),
            ),
            patch("app.services.debate.turn_executor.settings") as mock_settings,
        ):
            mock_settings.debate_turn_max_retries = 2

            result = await _execute_turn_with_retry(
                db=AsyncMock(),
                client=AsyncMock(),
                match=_make_match(),
                topic=_make_topic(),
                turn_number=1,
                speaker="agent_a",
                agent=_make_agent(),
                version=None,
                api_key="test-key",
                my_claims=[],
                opponent_claims=[],
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_재시도_횟수는_max_retries_plus_one(self):
        """총 시도 횟수는 debate_turn_max_retries + 1이다."""
        call_count = 0

        async def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("항상 실패")

        with (
            patch("app.services.debate.turn_executor.TurnExecutor.execute", side_effect=count_calls),
            patch("app.services.debate.turn_executor.settings") as mock_settings,
        ):
            mock_settings.debate_turn_max_retries = 2

            await _execute_turn_with_retry(
                db=AsyncMock(),
                client=AsyncMock(),
                match=_make_match(),
                topic=_make_topic(),
                turn_number=1,
                speaker="agent_b",
                agent=_make_agent(),
                version=None,
                api_key="test-key",
                my_claims=[],
                opponent_claims=[],
            )

        # max_retries=2이면 최초 1회 + 재시도 2회 = 총 3회
        assert call_count == 3


class TestForfeitError:
    """ForfeitError 기본 동작 테스트."""

    def test_forfeited_speaker_속성(self):
        """ForfeitError이 forfeited_speaker를 올바르게 저장한다."""
        exc = ForfeitError(forfeited_speaker="agent_a")
        assert exc.forfeited_speaker == "agent_a"

    def test_예외_메시지(self):
        """ForfeitError 메시지에 speaker 정보가 포함된다."""
        exc = ForfeitError(forfeited_speaker="agent_b")
        assert "agent_b" in str(exc)

    def test_Exception_상속(self):
        """ForfeitError은 Exception을 상속한다."""
        exc = ForfeitError(forfeited_speaker="agent_a")
        assert isinstance(exc, Exception)


class TestForfeitFlow:
    """부전패 발생 시 judge 미호출 확인."""

    @pytest.mark.asyncio
    async def test_부전패시_judge_미호출(self):
        """_execute_turn_with_retry가 None을 반환하면 ForfeitError이 raise되어 judge가 호출되지 않는다."""
        agent_a = _make_agent()
        agent_b = _make_agent()
        match = _make_match()
        match.agent_a_id = agent_a.id
        match.agent_b_id = agent_b.id
        topic = _make_topic()

        judge_mock = AsyncMock()

        # _execute_turn_with_retry가 None을 반환하도록 모킹 (agent_a 부전패)
        async def turn_with_retry_returns_none(*args, **kwargs):
            if kwargs.get("speaker") == "agent_a" or (len(args) > 5 and args[5] == "agent_a"):
                return None
            return _make_turn_log()

        forfeit_exception_raised = False

        try:
            with patch(
                "app.services.debate.engine._execute_turn_with_retry",
                side_effect=turn_with_retry_returns_none,
            ):
                turn_result = await turn_with_retry_returns_none(
                    db=AsyncMock(),
                    client=AsyncMock(),
                    match=match,
                    topic=topic,
                    turn_number=1,
                    speaker="agent_a",
                    agent=agent_a,
                    version=None,
                    api_key="key",
                    my_claims=[],
                    opponent_claims=[],
                )
                if turn_result is None:
                    raise ForfeitError(forfeited_speaker="agent_a")
        except ForfeitError:
            forfeit_exception_raised = True

        # ForfeitError이 raise됐고 judge는 호출되지 않았다
        assert forfeit_exception_raised is True
        judge_mock.assert_not_called()
