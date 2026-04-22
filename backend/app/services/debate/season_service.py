"""시즌 시스템 서비스 — 시즌 생성, 종료, 결과 조회."""

import logging
from datetime import datetime

from sqlalchemy import case as sa_case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent, DebateAgentSeasonStats
from app.models.debate_season import DebateSeason, DebateSeasonResult
from app.models.user import User
from app.services.debate.agent_service import get_tier_from_elo

logger = logging.getLogger(__name__)


class DebateSeasonService:
    """시즌 생성·종료, 에이전트별 시즌 ELO/전적 집계, 보상 지급 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_season(
        self, season_number: int, title: str, start_at: datetime, end_at: datetime
    ) -> DebateSeason:
        """새 시즌을 생성한다 (status='upcoming').

        Args:
            season_number: 시즌 번호 (1부터 증가).
            title: 시즌 제목.
            start_at: 시작 일시.
            end_at: 종료 일시.

        Returns:
            생성된 DebateSeason 객체.
        """
        season = DebateSeason(
            season_number=season_number,
            title=title,
            start_at=start_at,
            end_at=end_at,
            status="upcoming",
        )
        self.db.add(season)
        await self.db.commit()
        await self.db.refresh(season)
        return season

    async def get_active_season(self) -> DebateSeason | None:
        """status='active'인 시즌만 반환 (upcoming 제외)."""
        res = await self.db.execute(
            select(DebateSeason)
            .where(DebateSeason.status == "active")
            .order_by(DebateSeason.season_number.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def get_current_season(self) -> DebateSeason | None:
        """현재 시즌을 반환한다. active 우선, 없으면 가장 최신 upcoming.

        Returns:
            현재 시즌 DebateSeason. 없으면 None.
        """
        # active 우선, 없으면 가장 최신 upcoming — 단일 쿼리로 통합
        res = await self.db.execute(
            select(DebateSeason)
            .where(DebateSeason.status.in_(["active", "upcoming"]))
            .order_by(
                sa_case((DebateSeason.status == "active", 0), else_=1),
                DebateSeason.season_number.desc(),
            )
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def get_or_create_season_stats(
        self, agent_id: str, season_id: str
    ) -> DebateAgentSeasonStats:
        """에이전트의 시즌 통계 행을 가져오거나 생성 (ELO 1500, Iron 시작)."""
        res = await self.db.execute(
            select(DebateAgentSeasonStats).where(
                DebateAgentSeasonStats.agent_id == agent_id,
                DebateAgentSeasonStats.season_id == season_id,
            )
        )
        stats = res.scalar_one_or_none()
        if stats is None:
            try:
                # SAVEPOINT로 감싸 동시 INSERT 시 상위 트랜잭션 롤백 방지
                async with self.db.begin_nested():
                    stats = DebateAgentSeasonStats(
                        agent_id=agent_id,
                        season_id=season_id,
                        elo_rating=1500,
                        tier="Iron",
                    )
                    self.db.add(stats)
            except IntegrityError:
                # 동시 요청으로 이미 생성된 경우 재조회
                res = await self.db.execute(
                    select(DebateAgentSeasonStats).where(
                        DebateAgentSeasonStats.agent_id == agent_id,
                        DebateAgentSeasonStats.season_id == season_id,
                    )
                )
                stats = res.scalar_one()
        return stats

    async def update_season_stats(
        self, agent_id: str, season_id: str, new_elo: int, result_type: str
    ) -> None:
        """시즌 ELO/전적 갱신 + tier 재계산.

        result_type: 'win' | 'loss' | 'draw'

        시즌 ELO는 승급전/강등전 트리거와 무관하다.
        승급전/강등전은 누적 ELO(DebateAgent.elo_rating) 변화 기준으로만 트리거된다.
        """
        stats = await self.get_or_create_season_stats(agent_id, season_id)
        stats.elo_rating = new_elo
        stats.tier = get_tier_from_elo(new_elo)
        if result_type == "win":
            stats.wins += 1
        elif result_type == "loss":
            stats.losses += 1
        else:
            stats.draws += 1

    async def get_season_results(self, season_id: str) -> list[dict]:
        """시즌 최종 결과(순위·ELO·보상)를 반환한다.

        Args:
            season_id: 시즌 UUID 문자열.

        Returns:
            rank, agent_id, agent_name, final_elo, final_tier, wins, losses, draws,
            reward_credits 키를 포함한 dict 목록 (순위 오름차순).
        """
        res = await self.db.execute(
            select(DebateSeasonResult, DebateAgent)
            .join(DebateAgent, DebateSeasonResult.agent_id == DebateAgent.id)
            .where(DebateSeasonResult.season_id == season_id)
            .order_by(DebateSeasonResult.rank)
        )
        items = []
        for result, agent in res.all():
            items.append({
                "rank": result.rank,
                "agent_id": str(result.agent_id),
                "agent_name": agent.name,
                "agent_image_url": agent.image_url,
                "final_elo": result.final_elo,
                "final_tier": result.final_tier,
                "wins": result.wins,
                "losses": result.losses,
                "draws": result.draws,
                "reward_credits": result.reward_credits,
            })
        return items

    async def close_season(self, season_id: str) -> None:
        """시즌 종료: results INSERT → 보상 → ELO soft reset → tier 재계산."""

        res = await self.db.execute(select(DebateSeason).where(DebateSeason.id == season_id))
        season = res.scalar_one_or_none()
        if season is None:
            raise ValueError("Season not found")
        if season.status != "active":
            raise ValueError("활성 시즌만 종료할 수 있습니다")

        # 해당 시즌 참가 에이전트 시즌 ELO 내림차순 조회 (매치 0회 에이전트 제외)
        stats_res = await self.db.execute(
            select(DebateAgentSeasonStats, DebateAgent)
            .join(DebateAgent, DebateAgentSeasonStats.agent_id == DebateAgent.id)
            .where(
                DebateAgentSeasonStats.season_id == season.id,
                DebateAgent.is_active == True,  # noqa: E712
            )
            .order_by(DebateAgentSeasonStats.elo_rating.desc())
        )
        season_stats_rows = stats_res.all()

        # N+1 방지: 보상 지급 대상 User를 단일 배치 쿼리로 조회
        top3_rewards = settings.debate_season_reward_top3
        rank4_10_reward = settings.debate_season_reward_rank4_10

        owner_ids = {agent.owner_id for _, agent in season_stats_rows}
        owners_map: dict = {}
        if owner_ids:
            owners_res = await self.db.execute(select(User).where(User.id.in_(owner_ids)))
            owners_map = {str(u.id): u for u in owners_res.scalars()}

        # 시즌 참가 에이전트만 soft reset 적용 — 미참가 에이전트는 의도적으로 건드리지 않음
        # (시즌 참가 인센티브 설계: 시즌 참가자끼리의 ELO 격차를 다음 시즌 시작 전에 압축)
        for rank, (stats, agent) in enumerate(season_stats_rows, start=1):
            reward = top3_rewards[rank - 1] if rank <= len(top3_rewards) else (rank4_10_reward if rank <= 10 else 0)
            result = DebateSeasonResult(
                season_id=season.id,
                agent_id=agent.id,
                # 시즌 전적/ELO 기준으로 결과 저장
                final_elo=stats.elo_rating,
                final_tier=stats.tier,
                wins=stats.wins,
                losses=stats.losses,
                draws=stats.draws,
                rank=rank,
                reward_credits=reward,
            )
            self.db.add(result)

            # 보상 크레딧 실제 지급 — 배치 조회된 맵에서 O(1) 접근
            if reward > 0:
                owner = owners_map.get(str(agent.owner_id))
                if owner is not None:
                    owner.credit_balance += reward

            # 누적 ELO soft reset: (누적 elo + 1500) // 2
            new_elo = (agent.elo_rating + 1500) // 2
            agent.elo_rating = new_elo
            agent.tier = get_tier_from_elo(new_elo)

        season.status = "completed"
        await self.db.commit()
        logger.info("Season %s closed, %d agents ranked", season_id, len(season_stats_rows))
