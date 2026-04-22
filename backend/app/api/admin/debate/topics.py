"""관리자 토론 통계 · 정리 · 토픽 관리."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch, DebateMatchQueue
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.schemas.debate_topic import TopicUpdate
from app.services.debate.topic_service import DebateTopicService

router = APIRouter()


@router.get("/stats")
async def debate_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """토론 플랫폼 전체 통계."""
    agents_count = (await db.execute(select(func.count(DebateAgent.id)))).scalar() or 0
    topics_count = (await db.execute(select(func.count(DebateTopic.id)))).scalar() or 0
    matches_total = (await db.execute(select(func.count(DebateMatch.id)))).scalar() or 0
    matches_completed = (await db.execute(
        select(func.count(DebateMatch.id)).where(DebateMatch.status == "completed")
    )).scalar() or 0
    matches_in_progress = (await db.execute(
        select(func.count(DebateMatch.id)).where(DebateMatch.status == "in_progress")
    )).scalar() or 0

    return {
        "agents_count": agents_count,
        "topics_count": topics_count,
        "matches_total": matches_total,
        "matches_completed": matches_completed,
        "matches_in_progress": matches_in_progress,
    }


@router.patch("/topics/{topic_id}")
async def update_topic(
    topic_id: str,
    data: TopicUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """토픽 수정 (관리자)."""
    service = DebateTopicService(db)
    try:
        topic = await service.update_topic(topic_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "id": str(topic.id),
        "title": topic.title,
        "status": topic.status,
        "updated_at": topic.updated_at,
    }


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: str,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """토픽 삭제 (superadmin 전용, 매치가 없는 경우만)."""
    service = DebateTopicService(db)
    try:
        await service.delete_topic(topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_debate_state(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """대기 큐 및 묶인 매치를 즉시 정리 (superadmin 전용)."""
    queue_result = await db.execute(delete(DebateMatchQueue))
    deleted_queue = queue_result.rowcount

    match_result = await db.execute(
        sa_update(DebateMatch)
        .where(DebateMatch.status.in_(["pending", "waiting_agent"]))
        .values(status="error", finished_at=datetime.now(UTC))
        .returning(DebateMatch.id)
    )
    fixed_matches = len(match_result.fetchall())

    await db.commit()
    return {
        "deleted_queue_entries": deleted_queue,
        "fixed_stuck_matches": fixed_matches,
    }
