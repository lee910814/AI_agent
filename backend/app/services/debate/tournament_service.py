"""토너먼트 서비스 — 생성, 참가, 라운드 진행."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_tournament import DebateTournament, DebateTournamentEntry
from app.models.user import User

logger = logging.getLogger(__name__)


class DebateTournamentService:
    """토너먼트 생성, 참가, 라운드 진행, 조회 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tournament(
        self, title: str, topic_id: str, bracket_size: int, created_by: uuid.UUID
    ) -> DebateTournament:
        """토너먼트를 생성한다 (status='registration').

        Args:
            title: 토너먼트 제목.
            topic_id: 사용할 토픽 UUID 문자열.
            bracket_size: 참가 정원 (2의 제곱수 권장).
            created_by: 생성자 User UUID.

        Returns:
            생성된 DebateTournament 객체.
        """
        t = DebateTournament(
            title=title,
            topic_id=uuid.UUID(topic_id),
            bracket_size=bracket_size,
            created_by=created_by,
        )
        self.db.add(t)
        await self.db.commit()
        await self.db.refresh(t)
        return t

    async def join_tournament(
        self, tournament_id: str, agent_id: str, user: User
    ) -> DebateTournamentEntry:
        """토너먼트에 에이전트를 참가 등록한다.

        FOR UPDATE 잠금으로 동시 요청 시 정원 초과를 방지한다.

        Args:
            tournament_id: 참가할 토너먼트 UUID 문자열.
            agent_id: 참가시킬 에이전트 UUID 문자열.
            user: 현재 인증된 사용자 (소유권 검증용).

        Returns:
            생성된 DebateTournamentEntry 객체.

        Raises:
            ValueError: 토너먼트 미존재, 참가 기간 아님, 정원 초과, 'DUPLICATE'.
        """
        # 토너먼트 행 잠금 — 동시 참가 요청 시 bracket_size 초과 방지
        res = await self.db.execute(
            select(DebateTournament)
            .where(DebateTournament.id == tournament_id)
            .with_for_update()
        )
        t = res.scalar_one_or_none()
        if t is None:
            raise ValueError("Tournament not found")
        if t.status != "registration":
            raise ValueError("참가 신청 기간이 아닙니다")

        # 잠금 후 현재 참가자 수 재확인
        count_res = await self.db.execute(
            select(func.count(DebateTournamentEntry.id))
            .where(DebateTournamentEntry.tournament_id == tournament_id)
        )
        current_count = count_res.scalar() or 0
        if current_count >= t.bracket_size:
            raise ValueError("참가 정원이 가득 찼습니다")

        # 중복 확인
        dup = await self.db.execute(
            select(DebateTournamentEntry).where(
                and_(
                    DebateTournamentEntry.tournament_id == tournament_id,
                    DebateTournamentEntry.agent_id == agent_id,
                )
            )
        )
        if dup.scalar_one_or_none():
            raise ValueError("DUPLICATE")

        seed = current_count + 1

        entry = DebateTournamentEntry(
            tournament_id=uuid.UUID(tournament_id),
            agent_id=uuid.UUID(agent_id),
            seed=seed,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def advance_round(self, tournament_id: str) -> None:
        """현재 라운드 전체 완료 → 승자끼리 다음 라운드. 1명 남으면 토너먼트 종료."""
        res = await self.db.execute(
            select(DebateTournament).where(DebateTournament.id == tournament_id)
        )
        t = res.scalar_one_or_none()
        if t is None or t.status != "in_progress":
            return

        # 현재 라운드 매치 조회
        current_round_matches_res = await self.db.execute(
            select(DebateMatch).where(
                and_(
                    DebateMatch.tournament_id == tournament_id,
                    DebateMatch.tournament_round == t.current_round,
                )
            )
        )
        current_matches = list(current_round_matches_res.scalars().all())

        # 미완료 매치 있으면 스킵
        if any(m.status != "completed" for m in current_matches):
            return

        # 승자 목록: 승자 있으면 winner_id, 무승부면 agent_a가 진출
        winners = []
        for m in current_matches:
            if m.winner_id is not None:
                winners.append(m.winner_id)
            elif m.status == "completed":
                winners.append(m.agent_a_id)

        if len(winners) == 1:
            # 토너먼트 종료
            t.winner_agent_id = winners[0]
            t.status = "completed"
            t.finished_at = datetime.now(UTC)
            await self.db.commit()
            logger.info("Tournament %s completed, winner: %s", tournament_id, winners[0])
            return

        # 다음 라운드 매치 생성 (짝 짓기)
        next_round = t.current_round + 1
        for i in range(0, len(winners) - 1, 2):
            match = DebateMatch(
                topic_id=t.topic_id,
                agent_a_id=winners[i],
                agent_b_id=winners[i + 1],
                tournament_id=t.id,
                tournament_round=next_round,
            )
            self.db.add(match)

        t.current_round = next_round
        await self.db.commit()
        logger.info("Tournament %s advanced to round %d", tournament_id, next_round)

    async def get_tournament(self, tournament_id: str) -> dict | None:
        """토너먼트 상세 정보와 참가자 목록을 반환.

        Args:
            tournament_id: 토너먼트 UUID 문자열.

        Returns:
            id, title, status, entries 등을 포함한 dict. 미존재 시 None.
        """
        res = await self.db.execute(
            select(DebateTournament).where(DebateTournament.id == tournament_id)
        )
        t = res.scalar_one_or_none()
        if t is None:
            return None

        entries_res = await self.db.execute(
            select(DebateTournamentEntry, DebateAgent)
            .join(DebateAgent, DebateTournamentEntry.agent_id == DebateAgent.id)
            .where(DebateTournamentEntry.tournament_id == tournament_id)
            .order_by(DebateTournamentEntry.seed)
        )
        entries = [
            {
                "id": str(e.id),
                "agent_id": str(e.agent_id),
                "agent_name": a.name,
                "agent_image_url": a.image_url,
                "seed": e.seed,
                "eliminated_at": e.eliminated_at,
                "eliminated_round": e.eliminated_round,
            }
            for e, a in entries_res.all()
        ]

        return {
            "id": str(t.id),
            "title": t.title,
            "topic_id": str(t.topic_id),
            "status": t.status,
            "bracket_size": t.bracket_size,
            "current_round": t.current_round,
            "winner_agent_id": str(t.winner_agent_id) if t.winner_agent_id else None,
            "started_at": t.started_at,
            "finished_at": t.finished_at,
            "created_at": t.created_at,
            "entries": entries,
        }

    async def list_tournaments(self, skip: int = 0, limit: int = 20) -> tuple[list, int]:
        """토너먼트 목록을 최신순으로 반환.

        Args:
            skip: 건너뛸 항목 수.
            limit: 반환할 최대 항목 수.

        Returns:
            (items, total) 튜플. items는 토너먼트 요약 dict 목록, total은 전체 수.
        """
        count_res = await self.db.execute(select(func.count(DebateTournament.id)))
        total = count_res.scalar() or 0
        res = await self.db.execute(
            select(DebateTournament)
            .order_by(DebateTournament.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = [
            {
                "id": str(t.id),
                "title": t.title,
                "topic_id": str(t.topic_id),
                "status": t.status,
                "bracket_size": t.bracket_size,
                "current_round": t.current_round,
                "winner_agent_id": str(t.winner_agent_id) if t.winner_agent_id else None,
                "created_at": t.created_at,
            }
            for t in res.scalars().all()
        ]
        return items, total
