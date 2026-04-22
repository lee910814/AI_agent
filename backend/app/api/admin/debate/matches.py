"""관리자 토론 매치 관리 — 목록 조회, 디버그, 강제 매치, 하이라이트."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.user import User
from app.services.debate.agent_service import get_latest_version
from app.services.debate.match_service import DebateMatchService

router = APIRouter()


class ForceMatchRequest(BaseModel):
    """강제 매치 생성 요청 스키마."""

    agent_a_id: UUID
    agent_b_id: UUID


async def _run_debate_safe(match_id: str) -> None:
    """토론 엔진 실행 래퍼 (관리자 강제 매치용).

    Args:
        match_id: 실행할 매치 ID.
    """
    import logging as _logging

    from app.services.debate.engine import run_debate
    _logger = _logging.getLogger(__name__)
    try:
        await run_debate(match_id)
    except Exception:
        _logger.exception("토론 엔진 오류 (force-match, match_id=%s)", match_id)


@router.get("/matches")
async def list_all_matches(
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 매치 목록 (관리자). 차단된 턴 수 포함."""
    service = DebateMatchService(db)
    items, total = await service.list_matches(
        status=status_filter, skip=skip, limit=limit,
        search=search, date_from=date_from, date_to=date_to,
        include_test=True,
    )

    if items:
        match_ids = [item["id"] for item in items]
        blocked_result = await db.execute(
            select(DebateTurnLog.match_id, func.count(DebateTurnLog.id).label("cnt"))
            .where(
                DebateTurnLog.match_id.in_(match_ids),
                DebateTurnLog.is_blocked == True,  # noqa: E712
            )
            .group_by(DebateTurnLog.match_id)
        )
        blocked_map: dict = {str(row.match_id): row.cnt for row in blocked_result}
        for item in items:
            item["blocked_turns_count"] = blocked_map.get(item["id"], 0)

    return {"items": items, "total": total}


@router.get("/matches/{match_id}/debug")
async def get_match_debug(
    match_id: str,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """매치 전체 디버그 로그 (superadmin 전용 — 차단 원문 포함)."""
    row = (
        await db.execute(
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .where(DebateMatch.id == match_id)
        )
    ).one_or_none()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    match, topic_title = row
    agent_a = await db.get(DebateAgent, match.agent_a_id)
    agent_b = await db.get(DebateAgent, match.agent_b_id)

    turns = (
        await db.execute(
            select(DebateTurnLog)
            .where(DebateTurnLog.match_id == match.id)
            .order_by(DebateTurnLog.turn_number)
        )
    ).scalars().all()

    return {
        "match": {
            "id": str(match.id),
            "topic_title": topic_title,
            "agent_a": {
                "id": str(agent_a.id) if agent_a else str(match.agent_a_id),
                "name": agent_a.name if agent_a else "[삭제됨]",
                "provider": agent_a.provider if agent_a else "",
                "model_id": agent_a.model_id if agent_a else "",
            },
            "agent_b": {
                "id": str(agent_b.id) if agent_b else str(match.agent_b_id),
                "name": agent_b.name if agent_b else "[삭제됨]",
                "provider": agent_b.provider if agent_b else "",
                "model_id": agent_b.model_id if agent_b else "",
            },
            "status": match.status,
            "winner_id": str(match.winner_id) if match.winner_id else None,
            "score_a": match.score_a,
            "score_b": match.score_b,
            "penalty_a": match.penalty_a,
            "penalty_b": match.penalty_b,
            "scorecard": match.scorecard,
            "started_at": match.started_at,
            "finished_at": match.finished_at,
        },
        "turns": [
            {
                "id": str(t.id),
                "turn_number": t.turn_number,
                "speaker": t.speaker,
                "action": t.action,
                "claim": t.claim,
                "evidence": t.evidence,
                "raw_response": t.raw_response,
                "review_result": t.review_result,
                "penalties": t.penalties,
                "penalty_total": t.penalty_total,
                "is_blocked": t.is_blocked,
                "human_suspicion_score": t.human_suspicion_score,
                "response_time_ms": t.response_time_ms,
                "input_tokens": t.input_tokens,
                "output_tokens": t.output_tokens,
                "tool_used": t.tool_used,
                "tool_result": t.tool_result,
                "created_at": t.created_at,
            }
            for t in turns
        ],
    }


@router.post("/topics/{topic_id}/force-match", status_code=status.HTTP_201_CREATED)
async def force_match(
    topic_id: str,
    data: ForceMatchRequest,
    background_tasks: BackgroundTasks,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """강제 매치 생성 — 큐 없이 즉시 매칭 (superadmin 전용)."""
    topic = await db.get(DebateTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    if str(data.agent_a_id) == str(data.agent_b_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="두 에이전트가 같을 수 없습니다")

    agent_a = await db.get(DebateAgent, str(data.agent_a_id))
    agent_b = await db.get(DebateAgent, str(data.agent_b_id))
    if agent_a is None or agent_b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    ver_a = await get_latest_version(db, agent_a.id)
    ver_b = await get_latest_version(db, agent_b.id)

    match = DebateMatch(
        topic_id=topic_id,
        agent_a_id=agent_a.id,
        agent_b_id=agent_b.id,
        agent_a_version_id=ver_a.id if ver_a else None,
        agent_b_version_id=ver_b.id if ver_b else None,
        status="pending",
        is_test=True,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)

    background_tasks.add_task(_run_debate_safe, str(match.id))

    return {"match_id": str(match.id), "topic_id": topic_id}


@router.patch("/matches/{match_id}/feature")
async def toggle_match_feature(
    match_id: str,
    featured: bool,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """매치 하이라이트 설정/해제 (관리자)."""
    service = DebateMatchService(db)
    try:
        return await service.toggle_featured(match_id, featured)
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail) from exc
