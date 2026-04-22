"""부전패 예외 및 처리 클래스."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.services.debate.broadcast import publish_event
from app.services.debate.helpers import calculate_elo

logger = logging.getLogger(__name__)

# GC 수집 방지 — create_task() 반환 Task에 강한 참조를 유지한다
_background_tasks: set[asyncio.Task] = set()


class ForfeitError(Exception):
    """재시도를 모두 소진한 에이전트의 부전패를 알리는 예외.

    ForfeitHandler.handle_retry_exhaustion()에서 처리된다.

    Attributes:
        forfeited_speaker: 부전패 처리된 발언자 ('agent_a' | 'agent_b').
    """

    def __init__(self, forfeited_speaker: str) -> None:
        self.forfeited_speaker = forfeited_speaker
        super().__init__(f"Forfeit by {forfeited_speaker}")


async def _update_season_elo(
    db: AsyncSession,
    match: DebateMatch,
    agent_a: DebateAgent,
    agent_b: DebateAgent,
    elo_result: str,
    result_a: str,
    result_b: str,
    score_diff: int,
) -> tuple[float, float]:
    """시즌 ELO를 갱신하는 공통 헬퍼.

    MatchFinalizer와 ForfeitHandler 양쪽에서 동일 로직으로 사용한다.

    Args:
        db: 비동기 DB 세션.
        match: 완료된 매치 (season_id 참조).
        agent_a: A측 에이전트.
        agent_b: B측 에이전트.
        elo_result: 'a_win' | 'b_win' | 'draw'.
        result_a: A 결과 문자열 ('win' | 'loss' | 'draw').
        result_b: B 결과 문자열 ('win' | 'loss' | 'draw').
        score_diff: 점수차 절댓값 (ELO 배수 계산용).

    Returns:
        (new_season_elo_a, new_season_elo_b) 튜플.
    """
    from app.services.debate.helpers import calculate_elo
    from app.services.debate.season_service import DebateSeasonService

    season_svc = DebateSeasonService(db)
    stats_a = await season_svc.get_or_create_season_stats(str(agent_a.id), str(match.season_id))
    stats_b = await season_svc.get_or_create_season_stats(str(agent_b.id), str(match.season_id))
    new_a, new_b = calculate_elo(stats_a.elo_rating, stats_b.elo_rating, elo_result, score_diff=score_diff)
    await season_svc.update_season_stats(str(agent_a.id), str(match.season_id), new_a, result_a)
    await season_svc.update_season_stats(str(agent_b.id), str(match.season_id), new_b, result_b)
    return new_a, new_b


class ForfeitHandler:
    """부전패 처리 — 접속 미이행(handle_disconnect) + 재시도 소진(handle_retry_exhaustion)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def settle(
        self,
        match: DebateMatch,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
        elo_result: str,
        result_a: str,
        result_b: str,
        version_a_id: str | None = None,
        version_b_id: str | None = None,
    ) -> tuple[float, float, list[dict]]:
        """ELO·전적·시즌·승급전을 공통으로 처리한다.

        is_test=True 매치는 ELO/전적 갱신을 건너뛴다.

        Args:
            match: 처리할 매치.
            agent_a: A측 에이전트.
            agent_b: B측 에이전트.
            elo_result: 'a_win' | 'b_win' | 'draw'.
            result_a: A 결과 ('win' | 'loss' | 'draw').
            result_b: B 결과 ('win' | 'loss' | 'draw').
            version_a_id: A 버전 UUID 문자열 (없으면 None).
            version_b_id: B 버전 UUID 문자열 (없으면 None).

        Returns:
            (new_elo_a, new_elo_b, series_events) 튜플.
            series_events: commit 후 호출자가 직접 발행할 series_update 페이로드 목록.
        """
        from app.services.debate.agent_service import DebateAgentService
        from app.services.debate.promotion_service import DebatePromotionService

        new_a, new_b = calculate_elo(
            agent_a.elo_rating, agent_b.elo_rating, elo_result,
            score_diff=settings.debate_elo_forfeit_score_diff,
        )

        if match.is_test:
            return new_a, new_b, []

        agent_service = DebateAgentService(self.db)
        await agent_service.update_elo(str(agent_a.id), new_a, result_a, version_a_id)
        await agent_service.update_elo(str(agent_b.id), new_b, result_b, version_b_id)

        if match.season_id:
            await _update_season_elo(
                self.db, match, agent_a, agent_b, elo_result, result_a, result_b,
                score_diff=settings.debate_elo_forfeit_score_diff,
            )

        # series_update SSE는 호출자가 commit 후 직접 발행 — uncommitted 데이터 노출 방지
        promo_svc = DebatePromotionService(self.db)
        series_events: list[dict] = []
        for agent_obj, res in [(agent_a, result_a), (agent_b, result_b)]:
            active = await promo_svc.get_active_series(str(agent_obj.id))
            if active:
                series_result = await promo_svc.record_match_result(str(active.id), res)
                series_events.append(series_result)

        return new_a, new_b, series_events

    async def handle_disconnect(
        self,
        match: DebateMatch,
        loser: DebateAgent,
        winner: DebateAgent,
        side: str,
    ) -> None:
        """로컬 에이전트가 접속 제한 시간 내에 연결하지 못한 경우 부전패 처리.

        match.status를 'forfeit'으로 변경하고 SSE로 알림을 발행한다.

        Args:
            match: 처리할 매치.
            loser: 접속 실패한 에이전트 (부전패 측).
            winner: 상대 에이전트 (승자).
            side: 부전패 측 ('agent_a' | 'agent_b').
        """
        match.status = "forfeit"
        match.finished_at = datetime.now(UTC)
        match.winner_id = winner.id
        # flush으로 상태만 세션에 반영 — settle() 완료 후 단일 commit()
        await self.db.flush()

        if side == "agent_a":
            agent_a_obj, agent_b_obj = loser, winner
            elo_result, result_a, result_b = "b_win", "loss", "win"
        else:
            agent_a_obj, agent_b_obj = winner, loser
            elo_result, result_a, result_b = "a_win", "win", "loss"

        version_a_id = str(match.agent_a_version_id) if match.agent_a_version_id else None
        version_b_id = str(match.agent_b_version_id) if match.agent_b_version_id else None

        _, __, series_events = await self.settle(
            match, agent_a_obj, agent_b_obj, elo_result, result_a, result_b,
            version_a_id, version_b_id,
        )

        await self.db.commit()
        for se in series_events:
            await publish_event(str(match.id), "series_update", se)
        await publish_event(str(match.id), "forfeit", {
            "match_id": str(match.id),
            "reason": f"Agent {loser.name} did not connect in time",
            "winner_id": str(winner.id),
        })

        if settings.community_post_enabled:
            from app.services.community_service import generate_community_posts_task

            community_task = asyncio.create_task(generate_community_posts_task(str(match.id)))
            _background_tasks.add(community_task)
            community_task.add_done_callback(_background_tasks.discard)
            community_task.add_done_callback(
                lambda t: logger.warning("community_post_task failed (disconnect): %s", t.exception())
                if not t.cancelled() and t.exception() else None
            )

        logger.info("Match %s forfeit: agent %s did not connect", match.id, loser.name)

    async def handle_retry_exhaustion(
        self,
        match: DebateMatch,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
        forfeited_speaker: str,
    ) -> None:
        """재시도를 모두 소진한 에이전트의 부전패를 처리한다.

        judge() LLM 호출 없이 즉시 종료하며, 예측투표 정산까지 수행한다.

        Args:
            match: 처리할 매치.
            agent_a: A측 에이전트.
            agent_b: B측 에이전트.
            forfeited_speaker: 부전패 발언자 ('agent_a' | 'agent_b').
        """
        from app.services.debate.match_service import DebateMatchService

        if forfeited_speaker == "agent_a":
            forfeit_winner, forfeit_loser = agent_b, agent_a
            score_a, score_b = 0, 100
            elo_result, result_a, result_b = "b_win", "loss", "win"
        else:
            forfeit_winner, forfeit_loser = agent_a, agent_b
            score_a, score_b = 100, 0
            elo_result, result_a, result_b = "a_win", "win", "loss"

        elo_a_before = agent_a.elo_rating
        elo_b_before = agent_b.elo_rating

        # handle_disconnect와 통일 — forfeit 경로는 항상 "forfeit" 상태
        match.status = "forfeit"
        match.finished_at = datetime.now(UTC)
        match.winner_id = forfeit_winner.id
        match.score_a = score_a
        match.score_b = score_b

        # 부전패 scorecard — Scorecard UI에 판정 사유 표시용 (LLM 판정 없이 즉시 종료된 경우)
        _full = {"argumentation": 40, "rebuttal": 35, "strategy": 25}
        _zero = {"argumentation": 0, "rebuttal": 0, "strategy": 0}
        match.scorecard = {
            "agent_a": _zero if forfeited_speaker == "agent_a" else _full,
            "agent_b": _zero if forfeited_speaker == "agent_b" else _full,
            "reasoning": (
                f"부전패: {forfeit_loser.name}이(가) 발언에 실패하여 모든 재시도 기회를 소진했습니다. "
                f"{forfeit_winner.name}의 불전승으로 처리됩니다."
            ),
        }

        version_a_id = str(match.agent_a_version_id) if match.agent_a_version_id else None
        version_b_id = str(match.agent_b_version_id) if match.agent_b_version_id else None

        new_a, new_b, series_events = await self.settle(
            match, agent_a, agent_b, elo_result, result_a, result_b,
            version_a_id, version_b_id,
        )

        await self.db.execute(
            update(DebateMatch)
            .where(DebateMatch.id == match.id)
            .values(elo_a_before=elo_a_before, elo_b_before=elo_b_before, elo_a_after=new_a, elo_b_after=new_b)
        )
        await self.db.commit()

        for se in series_events:
            try:
                await publish_event(str(match.id), "series_update", se)
            except Exception:
                logger.warning("series_update SSE failed for match %s", match.id, exc_info=True)

        try:
            await publish_event(str(match.id), "forfeit", {
                "forfeited_speaker": forfeited_speaker,
                "winner_id": str(forfeit_winner.id),
                "loser_id": str(forfeit_loser.id),
                "reason": "Turn execution failed after all retries",
            })
        except Exception:
            logger.warning("forfeit SSE failed for match %s", match.id, exc_info=True)

        try:
            await publish_event(str(match.id), "finished", {
                "winner_id": str(forfeit_winner.id),
                "score_a": score_a,
                "score_b": score_b,
                "elo_a_before": elo_a_before,
                "elo_a_after": new_a,
                "elo_b_before": elo_b_before,
                "elo_b_after": new_b,
                # 하위 호환
                "elo_a": new_a,
                "elo_b": new_b,
            })
        except Exception:
            logger.warning("finished SSE failed for match %s", match.id, exc_info=True)

        # commit 후 예외 시 outer handler가 "error"로 덮어쓰지 않도록 non-fatal 처리
        match_service = DebateMatchService(self.db)
        try:
            await match_service.resolve_predictions(
                str(match.id),
                str(forfeit_winner.id),
                str(match.agent_a_id),
                str(match.agent_b_id),
            )
        except Exception:
            logger.error("resolve_predictions failed for match %s — skipping", match.id, exc_info=True)

        if settings.community_post_enabled:
            from app.services.community_service import generate_community_posts_task

            community_task = asyncio.create_task(generate_community_posts_task(str(match.id)))
            _background_tasks.add(community_task)
            community_task.add_done_callback(_background_tasks.discard)
            community_task.add_done_callback(
                lambda t: logger.warning("community_post_task failed (retry_exhaustion): %s", t.exception())
                if not t.cancelled() and t.exception() else None
            )

        logger.info(
            "Match %s ended by forfeit. %s failed after retries, winner: %s",
            match.id, forfeit_loser.name, forfeit_winner.name,
        )
