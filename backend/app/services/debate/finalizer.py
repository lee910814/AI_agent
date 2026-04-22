"""매치 완료 후처리 통합 — ELO, 시즌, 승급전, SSE, DB 커밋, 예측, 토너먼트, 요약."""

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
from app.services.debate.forfeit import _update_season_elo
from app.services.debate.helpers import calculate_elo

logger = logging.getLogger(__name__)

# 백그라운드 태스크 강한 참조 보관 — GC가 완료 전 수거하지 못하도록 모듈 레벨에서 관리
_background_tasks: set[asyncio.Task] = set()


class MatchFinalizer:
    """매치 완료 후처리를 통합 관리하는 클래스.

    1v1·멀티 포맷 공통 진입점. ELO 갱신 → 시즌 → 승급전 → 커밋 → SSE → 예측투표 → 토너먼트 → 요약 순으로 처리한다.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def finalize(
        self,
        match: DebateMatch,
        judgment: dict,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
        model_cache: dict,
        usage_batch: list,
    ) -> None:
        """처리 순서:
        1. judge 토큰 usage_batch 추가
        2. ELO 계산 + DB 갱신
        3. 시즌 ELO 갱신 (match.season_id 있을 때만)
        4. 승급전/강등전 결과 반영 (멀티 경로 누락 버그 수정)
        5. DB 커밋 + usage_batch 일괄 INSERT
        6. finished SSE 발행 (커밋 후 — 새로고침 시 DB 결과와 항상 일치)
        7. 예측투표 정산
        8. 토너먼트 라운드 진행
        9. 요약 리포트 백그라운드 태스크
        10. 커뮤니티 포스트 백그라운드 태스크
        """
        # 중복 완료 처리 방어 — 동일 match에 finalize()가 두 번 호출될 경우 ELO 이중 반영 차단
        if match.status == "completed":
            logger.warning("finalize() called on already-completed match %s, skipping", match.id)
            return

        from app.services.debate.agent_service import DebateAgentService
        from app.services.debate.debate_formats import _log_orchestrator_usage
        from app.services.debate.match_service import DebateMatchService, generate_summary_task
        from app.services.debate.promotion_service import DebatePromotionService

        # 1. Judge 토큰 usage_batch 추가 (조기 커밋 버그 수정 — 판정 전 커밋하지 않음)
        await _log_orchestrator_usage(
            self.db, agent_a.owner_id, judgment.get("model_id", ""),
            judgment["input_tokens"], judgment["output_tokens"],
            model_cache=model_cache, usage_batch=usage_batch,
            match_id=match.id,
        )

        # 2. ELO 계산
        winner_id_str = str(judgment["winner_id"]) if judgment["winner_id"] else None
        if winner_id_str == str(match.agent_a_id):
            elo_result = "a_win"
        elif winner_id_str == str(match.agent_b_id):
            elo_result = "b_win"
        else:
            elo_result = "draw"

        score_diff = abs(judgment["score_a"] - judgment["score_b"])
        elo_a_before = agent_a.elo_rating
        elo_b_before = agent_b.elo_rating
        new_a, new_b = calculate_elo(elo_a_before, elo_b_before, elo_result, score_diff=score_diff)

        match.scorecard = judgment["scorecard"]
        match.score_a = judgment["score_a"]
        match.score_b = judgment["score_b"]
        match.winner_id = judgment["winner_id"]
        match.status = "completed"
        match.finished_at = datetime.now(UTC)

        result_a = "win" if elo_result == "a_win" else ("loss" if elo_result == "b_win" else "draw")
        result_b = "win" if elo_result == "b_win" else ("loss" if elo_result == "a_win" else "draw")

        agent_service = DebateAgentService(self.db)
        series_updates: list[dict] = []  # is_test=True 경로에서도 참조 가능하도록 최상단 초기화
        if not match.is_test:
            # version_id 전달 버그 수정 (멀티 경로에서 미전달됐던 issue)
            version_a_id = str(match.agent_a_version_id) if match.agent_a_version_id else None
            version_b_id = str(match.agent_b_version_id) if match.agent_b_version_id else None
            if not judgment.get("elo_suppressed"):
                await agent_service.update_elo(str(agent_a.id), new_a, result_a, version_a_id)
                await agent_service.update_elo(str(agent_b.id), new_b, result_b, version_b_id)

                # 3. 시즌 ELO 갱신
                if match.season_id:
                    await _update_season_elo(
                        self.db, match, agent_a, agent_b, elo_result, result_a, result_b, score_diff,
                    )

                # 4. 승급전/강등전 결과 반영 — elo_suppressed 시 실제 ELO 미갱신이므로 건너뜀
                # (elo_suppressed 블록 바깥에 두면 가상 ELO로 승급전 트리거가 잘못 발생함)
                promo_svc = DebatePromotionService(self.db)
                for agent_obj, res, elo_before, elo_after in [
                    (agent_a, result_a, elo_a_before, new_a),
                    (agent_b, result_b, elo_b_before, new_b),
                ]:
                    active = await promo_svc.get_active_series(str(agent_obj.id))
                    if active:
                        series_result = await promo_svc.record_match_result(str(active.id), res)
                        series_updates.append(series_result)
                        # 시리즈 완료 후 같은 매치의 ELO로 새 시리즈 트리거 기회 제공 (최대 1회)
                        if series_result.get("status") in ("won", "lost", "expired"):
                            post_tier = series_result.get("new_tier") or agent_obj.tier
                            if series_result.get("tier_changed") and series_result["series_type"] == "promotion":
                                post_protection = 3
                            elif series_result["series_type"] == "demotion" and series_result["status"] == "won":
                                post_protection = 1
                            else:
                                post_protection = 0
                            new_series = await promo_svc.check_and_trigger(
                                str(agent_obj.id), int(elo_before), int(elo_after), post_tier, post_protection,
                            )
                            if new_series:
                                series_updates.append({
                                    "id": str(new_series.id),
                                    "series_id": str(new_series.id),
                                    "agent_id": str(new_series.agent_id),
                                    "series_type": new_series.series_type,
                                    "status": new_series.status,
                                    "current_wins": 0,
                                    "current_losses": 0,
                                    "draw_count": 0,
                                    "required_wins": new_series.required_wins,
                                    "from_tier": new_series.from_tier,
                                    "to_tier": new_series.to_tier,
                                    "tier_changed": False,
                                    "new_tier": None,
                                })
            else:
                logger.info("ELO·승급전 갱신 skip — fallback 판정 (elo_suppressed=True), match=%s", match.id)

        # 5. DB 커밋 + usage_batch 일괄 INSERT — SSE 발행 전 커밋으로 데이터 정합성 보장
        # is_test 매치는 ELO 컬럼 기록 생략 (랭킹에 영향 없도록)
        if not match.is_test:
            await self.db.execute(
                update(DebateMatch)
                .where(DebateMatch.id == match.id)
                .values(
                    elo_a_before=elo_a_before,
                    elo_b_before=elo_b_before,
                    elo_a_after=new_a,
                    elo_b_after=new_b,
                )
            )
        if usage_batch:
            self.db.add_all(usage_batch)
        await self.db.commit()

        # 6. finished SSE 발행 — 커밋 완료 후 발행하여 새로고침 시에도 DB 결과와 일치
        # series_update 이전에 발행 — 완료 신호가 먼저 도착해야 프론트가 올바른 순서로 처리 가능
        # SSE 실패를 삼켜 run_debate() except Exception이 match.status를 'error'로 덮어쓰지 않도록 보호
        try:
            await publish_event(str(match.id), "finished", {
                "winner_id": str(judgment["winner_id"]) if judgment["winner_id"] else None,
                "score_a": judgment["score_a"],
                "score_b": judgment["score_b"],
                "elo_a_before": elo_a_before,
                "elo_a_after": new_a,
                "elo_b_before": elo_b_before,
                "elo_b_after": new_b,
                # 하위 호환
                "elo_a": new_a,
                "elo_b": new_b,
            })
        except Exception as exc:
            logger.error("finished SSE failed for match %s: %s", match.id, exc)

        # series_update SSE: finished 이후 발행 — 승급전 결과는 완료 화면 위에 오버레이로 표시
        for su in series_updates:
            try:
                await publish_event(str(match.id), "series_update", su)
            except Exception as exc:
                logger.error("series_update SSE failed for match %s: %s", match.id, exc)

        # 7. 예측투표 정산 — commit 후 독립 단계. 실패해도 후속 단계 진행
        match_service = DebateMatchService(self.db)
        try:
            await match_service.resolve_predictions(
                str(match.id),
                str(match.winner_id) if match.winner_id else None,
                str(match.agent_a_id),
                str(match.agent_b_id),
            )
        except Exception as exc:
            logger.error("resolve_predictions failed for match %s: %s", match.id, exc)

        # 8. 토너먼트 라운드 진행 — 실패해도 매치 완료 상태에 영향 없음
        if match.tournament_id:
            from app.services.debate.tournament_service import DebateTournamentService
            t_service = DebateTournamentService(self.db)
            try:
                await t_service.advance_round(str(match.tournament_id))
            except Exception as exc:
                logger.error("advance_round failed for match %s tournament %s: %s", match.id, match.tournament_id, exc)

        # 9. 요약 리포트 백그라운드 태스크 — 모듈 레벨 set에 보관하여 GC 수거 방지
        if settings.debate_summary_enabled:
            task = asyncio.create_task(generate_summary_task(str(match.id)))
            _background_tasks.add(task)

            def _on_summary_done(t: asyncio.Task, mid: str = str(match.id)) -> None:
                _background_tasks.discard(t)
                if not t.cancelled() and (exc := t.exception()):
                    logger.warning("Summary task failed for match %s: %s", mid, exc)

            task.add_done_callback(_on_summary_done)

        # 10. 커뮤니티 포스트 백그라운드 태스크
        if settings.community_post_enabled:
            from app.services.community_service import generate_community_posts_task

            community_task = asyncio.create_task(generate_community_posts_task(str(match.id)))
            _background_tasks.add(community_task)

            def _on_community_done(t: asyncio.Task, mid: str = str(match.id)) -> None:
                _background_tasks.discard(t)
                if not t.cancelled() and (exc := t.exception()):
                    logger.warning("community_post_task failed for match %s: %s", mid, exc)

            community_task.add_done_callback(_on_community_done)

        logger.info("Match %s completed. Winner: %s", match.id, judgment["winner_id"])
