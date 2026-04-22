"""관리자 토너먼트 관리."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_superadmin
from app.models.debate_tournament import DebateTournament
from app.models.user import User
from app.schemas.debate_tournament import TournamentCreate
from app.services.debate.tournament_service import DebateTournamentService

router = APIRouter()


@router.post("/tournaments", status_code=status.HTTP_201_CREATED)
async def create_tournament(
    data: TournamentCreate,
    user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """토너먼트 생성 (superadmin 전용)."""
    service = DebateTournamentService(db)
    t = await service.create_tournament(
        title=data.title,
        topic_id=str(data.topic_id),
        bracket_size=data.bracket_size,
        created_by=user.id,
    )
    return {"id": str(t.id)}


@router.post("/tournaments/{tournament_id}/start")
async def start_tournament(
    tournament_id: str,
    user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """토너먼트 시작 (superadmin 전용)."""
    t = (
        await db.execute(select(DebateTournament).where(DebateTournament.id == tournament_id))
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    if t.status != "registration":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 시작된 토너먼트입니다")
    t.status = "in_progress"
    t.current_round = 1
    t.started_at = datetime.now(UTC)
    await db.commit()
    return {"ok": True}
