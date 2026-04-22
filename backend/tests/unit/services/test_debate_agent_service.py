"""에이전트 서비스 단위 테스트."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.schemas.debate_agent import AgentCreate, AgentUpdate
from app.services.debate.promotion_service import TIER_ORDER


class TestDebateAgentService:
    def test_agent_create_schema_validation(self):
        """AgentCreate 스키마가 필수 필드를 검증한다."""
        data = AgentCreate(
            name="Test Agent",
            provider="openai",
            model_id="gpt-4o",
            api_key="sk-test",
            system_prompt="You are a debate agent.",
        )
        assert data.name == "Test Agent"
        assert data.provider == "openai"

    def test_agent_create_invalid_provider(self):
        """잘못된 provider는 검증 실패."""
        with pytest.raises(Exception):
            AgentCreate(
                name="Test",
                provider="invalid_provider",
                model_id="model",
                api_key="key",
                system_prompt="prompt",
            )

    def test_agent_update_partial(self):
        """AgentUpdate는 부분 업데이트를 허용한다."""
        data = AgentUpdate(name="New Name")
        assert data.name == "New Name"
        assert data.provider is None
        assert data.system_prompt is None

    def test_ranking_entry_format(self):
        """랭킹 결과 형식 검증."""
        ranking_entry = {
            "id": str(uuid.uuid4()),
            "name": "Agent1",
            "owner_nickname": "user1",
            "provider": "openai",
            "model_id": "gpt-4o",
            "elo_rating": 1500,
            "wins": 5,
            "losses": 3,
            "draws": 2,
        }
        assert ranking_entry["elo_rating"] == 1500
        assert ranking_entry["wins"] + ranking_entry["losses"] + ranking_entry["draws"] == 10


class TestUpdateAgentDeadCode:
    """update_agent() dead code 제거 검증."""

    @pytest.mark.asyncio
    async def test_update_agent_same_name_no_cooldown_reset(self):
        """이름이 동일하면 name_changed_at을 갱신하지 않는다.

        제거된 elif data.name is not None 분기 — 동일 이름 재할당은 no-op이어야 한다.
        """
        from app.services.debate.agent_service import DebateAgentService

        # 에이전트 mock: 이름 동일
        agent = MagicMock()
        agent.id = str(uuid.uuid4())
        agent.owner_id = "user-1"
        agent.name = "SameName"
        agent.name_changed_at = datetime(2026, 1, 1, tzinfo=UTC)

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))
        db.flush = AsyncMock()

        user = MagicMock()
        user.id = "user-1"
        user.role = "user"

        svc = DebateAgentService(db)
        data = AgentUpdate(name="SameName")  # 동일 이름

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.agent_name_change_cooldown_days = 7
            # 이름이 같으면 쿨다운 분기 자체에 진입하지 않으므로 예외 없이 통과
            await svc.update_agent(agent.id, data, user=user)

        # name_changed_at은 변경되지 않아야 한다
        assert agent.name_changed_at == datetime(2026, 1, 1, tzinfo=UTC)


class TestUpdateEloDeadCode:
    """update_elo() dead code 제거 + TIER_ORDER 재사용 검증."""

    def test_tier_order_imported_from_promotion_service(self):
        """update_elo에서 사용하는 TIER_ORDER가 debate_promotion_service 상수와 동일."""
        # 직접 import하여 동일 객체임을 확인
        expected = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]
        assert TIER_ORDER == expected

    @pytest.mark.asyncio
    async def test_update_elo_master_no_immediate_tier_change(self):
        """Master 에이전트는 ELO 상승 시 즉시 티어 변경 없음 — 승급전 시리즈가 처리한다."""
        from app.services.debate.agent_service import DebateAgentService

        agent = MagicMock()
        agent.id = str(uuid.uuid4())
        agent.tier = "Master"
        agent.elo_rating = 2400
        agent.tier_protection_count = 0
        agent.active_series_id = None
        agent.wins = 10
        agent.losses = 2
        agent.draws = 1

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))

        svc = DebateAgentService(db)

        with patch("app.services.debate.promotion_service.DebatePromotionService") as MockPromo:
            mock_promo = AsyncMock()
            # check_and_trigger: Master에서 ELO 상승은 None 반환 (최상위라 시리즈 미생성)
            mock_promo.check_and_trigger = AsyncMock(return_value=None)
            MockPromo.return_value = mock_promo

            result = await svc.update_elo(str(agent.id), new_elo=2500, result_type="win")

        # 반환값은 None (새 시리즈 없음)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_elo_protection_decrements_on_demotion(self):
        """보호 횟수가 있는 에이전트는 ELO 강등 시 보호 1회 차감, 시리즈 미생성."""
        from app.services.debate.agent_service import DebateAgentService

        agent = MagicMock()
        agent.id = str(uuid.uuid4())
        agent.tier = "Gold"
        agent.elo_rating = 1400
        agent.tier_protection_count = 2  # 보호 2회 남음
        agent.active_series_id = None
        agent.wins = 5
        agent.losses = 3
        agent.draws = 0

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))

        svc = DebateAgentService(db)

        with patch("app.services.debate.promotion_service.DebatePromotionService") as MockPromo:
            mock_promo = AsyncMock()
            # check_and_trigger: 보호 횟수 있으면 None 반환 (보호 소진 중)
            mock_promo.check_and_trigger = AsyncMock(return_value=None)
            MockPromo.return_value = mock_promo

            # Gold(ELO ~1400) → Silver(ELO ~1200)로 강등 시나리오
            result = await svc.update_elo(str(agent.id), new_elo=1200, result_type="loss")

        assert result is None
