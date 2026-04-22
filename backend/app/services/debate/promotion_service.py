"""승급전/강등전 시리즈 서비스.

ELO가 티어 경계를 넘을 때 즉시 승급/강등하는 대신
- 승급전: 3판 2선승(required_wins=2)
- 강등전: 1판 필승(required_wins=1)
시리즈를 생성하여 결과에 따라 티어를 결정한다.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent
from app.models.debate_promotion_series import DebatePromotionSeries

logger = logging.getLogger(__name__)

# 티어 순서 — 인덱스가 낮을수록 하위 티어. idx 비교로 승급/강등 방향을 판별
# check_and_trigger()에서 new_idx > old_idx → 승급, new_idx < old_idx → 강등
TIER_ORDER = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]


class DebatePromotionService:
    """승급전/강등전 시리즈 생성, 결과 기록, 취소, 트리거 판정 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_series(self, agent_id: str) -> DebatePromotionSeries | None:
        """에이전트의 현재 활성 시리즈를 조회한다.

        Args:
            agent_id: 에이전트 UUID 문자열.

        Returns:
            활성(status='active') DebatePromotionSeries. 없으면 None.
        """
        result = await self.db.execute(
            select(DebatePromotionSeries)
            .where(
                DebatePromotionSeries.agent_id == agent_id,
                DebatePromotionSeries.status == "active",
            )
            .order_by(DebatePromotionSeries.created_at.desc())
            .limit(1)  # MultipleResultsFound 방어 — active 시리즈가 2개 이상이면 최신 반환
        )
        return result.scalar_one_or_none()

    async def get_series_history(
        self, agent_id: str, limit: int = 20, offset: int = 0
    ) -> list[DebatePromotionSeries]:
        """에이전트의 시리즈 이력을 최신순으로 반환.

        Args:
            agent_id: 에이전트 UUID 문자열.
            limit: 반환할 최대 개수.
            offset: 건너뛸 항목 수.

        Returns:
            DebatePromotionSeries 목록 (생성 역순).
        """
        result = await self.db.execute(
            select(DebatePromotionSeries)
            .where(DebatePromotionSeries.agent_id == agent_id)
            .order_by(DebatePromotionSeries.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def _create_series(
        self, agent_id: str, series_type: str, from_tier: str, to_tier: str, required_wins: int
    ) -> DebatePromotionSeries:
        """시리즈 생성 공통 로직. 승급/강등 모두 이 메서드를 거친다."""
        series = DebatePromotionSeries(
            agent_id=agent_id,
            series_type=series_type,
            from_tier=from_tier,
            to_tier=to_tier,
            required_wins=required_wins,
        )
        self.db.add(series)
        await self.db.flush()  # ID 확보

        await self.db.execute(
            update(DebateAgent)
            .where(DebateAgent.id == agent_id)
            .values(active_series_id=series.id)
        )
        logger.info("%s series created: agent=%s %s→%s", series_type, agent_id, from_tier, to_tier)
        return series

    async def create_promotion_series(
        self, agent_id: str, from_tier: str, to_tier: str
    ) -> DebatePromotionSeries:
        """승급전 시리즈 생성 (required_wins=2, 3판 2선승)."""
        return await self._create_series(agent_id, "promotion", from_tier, to_tier, required_wins=2)

    async def create_demotion_series(
        self, agent_id: str, from_tier: str, to_tier: str
    ) -> DebatePromotionSeries:
        """강등전 시리즈 생성 (required_wins=1, 1판 필승)."""
        return await self._create_series(agent_id, "demotion", from_tier, to_tier, required_wins=1)

    async def record_match_result(self, series_id: str, result: str) -> dict:
        """시리즈에 매치 결과를 기록하고 시리즈 종료 여부를 반환.

        result: 'win' | 'loss' | 'draw'

        반환 dict:
          series_type, status, current_wins, current_losses, draw_count,
          required_wins, tier_changed, new_tier (optional)
        """
        res = await self.db.execute(
            select(DebatePromotionSeries).where(DebatePromotionSeries.id == series_id)
        )
        series = res.scalar_one_or_none()
        # 시리즈가 없거나 이미 완료/취소된 경우 기록 거부 — 중복 처리 방지
        if series is None or series.status != "active":
            return {"status": "not_found"}

        if result == "win":
            series.current_wins += 1
        elif result == "loss":
            series.current_losses += 1
        else:  # draw
            series.draw_count += 1
            if series.draw_count >= settings.debate_series_max_draws:
                series.status = "expired"
                series.completed_at = datetime.now(UTC)
                await self.db.execute(
                    update(DebateAgent)
                    .where(DebateAgent.id == str(series.agent_id))
                    .values(active_series_id=None)
                )
                return {
                    "id": str(series.id),
                    "series_id": str(series.id),
                    "agent_id": str(series.agent_id),
                    "series_type": series.series_type,
                    "status": "expired",
                    "current_wins": series.current_wins,
                    "current_losses": series.current_losses,
                    "draw_count": series.draw_count,
                    "required_wins": series.required_wins,
                    "from_tier": series.from_tier,
                    "to_tier": series.to_tier,
                    "tier_changed": False,
                    "new_tier": None,
                }
            # max_draws 미만: 시리즈 계속 진행
            return {
                "id": str(series.id),
                "series_id": str(series.id),
                "agent_id": str(series.agent_id),
                "series_type": series.series_type,
                "status": series.status,
                "current_wins": series.current_wins,
                "current_losses": series.current_losses,
                "draw_count": series.draw_count,
                "required_wins": series.required_wins,
                "from_tier": series.from_tier,
                "to_tier": series.to_tier,
                "tier_changed": False,
                "new_tier": None,
            }

        # 시리즈 종료 조건 판정
        series_done = False
        series_won = False
        # 강등전: 1판 필승 — 1패 즉시 강등 (max_losses=0)
        # 승급전: 3판 2선승 — 1패까지 허용 (max_losses=1)
        max_losses = 0 if series.series_type == "demotion" else 3 - series.required_wins

        # 필요 승수에 도달하면 시리즈 승리 확정
        if series.current_wins >= series.required_wins:
            series_done = True
            series_won = True
        # 허용 패수를 초과하면 시리즈 패배 확정
        elif series.current_losses > max_losses:
            series_done = True
            series_won = False

        tier_changed = False
        new_tier: str | None = None

        # 시리즈가 종료된 경우에만 티어 변경 및 에이전트 상태 갱신
        if series_done:
            series.status = "won" if series_won else "lost"
            series.completed_at = datetime.now(UTC)

            if series.series_type == "promotion":
                if series_won:
                    # 승급 성공: to_tier로 변경 + 보호 3회
                    await self.db.execute(
                        update(DebateAgent)
                        .where(DebateAgent.id == str(series.agent_id))
                        .values(
                            tier=series.to_tier,
                            tier_protection_count=3,
                            active_series_id=None,
                        )
                    )
                    tier_changed = True
                    new_tier = series.to_tier
                else:
                    # 승급 실패: 티어 유지
                    await self.db.execute(
                        update(DebateAgent)
                        .where(DebateAgent.id == str(series.agent_id))
                        .values(active_series_id=None)
                    )
            else:  # demotion
                if series_won:
                    # 강등전 생존: 티어 유지 + 보호 1회 보상
                    await self.db.execute(
                        update(DebateAgent)
                        .where(DebateAgent.id == str(series.agent_id))
                        .values(
                            tier_protection_count=1,
                            active_series_id=None,
                        )
                    )
                else:
                    # 강등 확정
                    await self.db.execute(
                        update(DebateAgent)
                        .where(DebateAgent.id == str(series.agent_id))
                        .values(
                            tier=series.to_tier,
                            active_series_id=None,
                        )
                    )
                    tier_changed = True
                    new_tier = series.to_tier

        return {
            "id": str(series.id),
            "series_id": str(series.id),
            "agent_id": str(series.agent_id),
            "series_type": series.series_type,
            "status": series.status,
            "current_wins": series.current_wins,
            "current_losses": series.current_losses,
            "draw_count": series.draw_count,
            "required_wins": series.required_wins,
            "from_tier": series.from_tier,
            "to_tier": series.to_tier,
            "tier_changed": tier_changed,
            "new_tier": new_tier,
        }

    async def cancel_series(self, agent_id: str) -> None:
        """에이전트의 활성 시리즈를 취소한다.

        에이전트 비활성화·탈퇴 등 시리즈를 강제 종료해야 할 때 사용.

        Args:
            agent_id: 에이전트 UUID 문자열.
        """
        series = await self.get_active_series(agent_id)
        if series is None:
            return
        series.status = "cancelled"
        series.completed_at = datetime.now(UTC)
        await self.db.execute(
            update(DebateAgent)
            .where(DebateAgent.id == agent_id)
            .values(active_series_id=None)
        )
        logger.info("Series cancelled: agent=%s series=%s", agent_id, series.id)

    async def check_and_trigger(
        self,
        agent_id: str,
        old_elo: int,
        new_elo: int,
        current_tier: str,
        protection_count: int,
    ) -> DebatePromotionSeries | None:
        """ELO 변화로 승급전/강등전 트리거 여부를 확인하고 시리즈를 생성.

        이미 활성 시리즈가 있으면 생성하지 않는다.
        Iron 강등 / Master 승급은 한계이므로 미생성.
        """
        from app.services.debate.agent_service import get_tier_from_elo

        old_tier = current_tier
        new_tier = get_tier_from_elo(new_elo)
        old_idx = TIER_ORDER.index(old_tier) if old_tier in TIER_ORDER else 0
        new_idx = TIER_ORDER.index(new_tier) if new_tier in TIER_ORDER else 0

        # ELO가 같은 티어 범위 내에 있으면 승급/강등 트리거 조건 미충족
        if old_idx == new_idx:
            return None

        # 이미 활성 시리즈가 있으면 새 시리즈 미생성
        existing = await self.get_active_series(agent_id)
        # 진행 중인 시리즈가 완료되기 전에 중복 시리즈를 생성하지 않음
        if existing is not None:
            return None

        if new_idx > old_idx:
            # 승급 조건: Master는 이미 최상위이므로 미생성
            if old_tier == "Master":
                return None
            next_tier = TIER_ORDER[old_idx + 1]
            return await self.create_promotion_series(agent_id, old_tier, next_tier)
        else:
            # 강등 조건: Iron은 이미 최하위이므로 미생성
            if old_tier == "Iron":
                return None
            # 보호 횟수가 남아있으면 보호를 먼저 소진 — 시리즈 없이 이번 강등을 막음
            if protection_count > 0:
                # 보호 횟수 소진은 여기서 직접 처리 — 호출자가 별도로 차감할 필요 없음
                await self.db.execute(
                    update(DebateAgent)
                    .where(DebateAgent.id == agent_id)
                    .values(tier_protection_count=DebateAgent.tier_protection_count - 1)
                )
                return None
            prev_tier = TIER_ORDER[old_idx - 1]
            return await self.create_demotion_series(agent_id, old_tier, prev_tier)
