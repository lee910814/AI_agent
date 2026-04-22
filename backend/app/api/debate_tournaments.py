"""토너먼트 API 라우터."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.debate.tournament_service import DebateTournamentService

router = APIRouter()


@router.get("")
async def list_tournaments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토너먼트 목록 조회."""
    service = DebateTournamentService(db)
    items, total = await service.list_tournaments(skip=skip, limit=limit)
    return {"items": items, "total": total}


@router.get("/{tournament_id}")
async def get_tournament(
    tournament_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토너먼트 상세 조회 (참가자 목록 포함)."""
    service = DebateTournamentService(db)
    t = await service.get_tournament(tournament_id)
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return t


@router.post("/{tournament_id}/join", status_code=status.HTTP_201_CREATED)
async def join_tournament(
    tournament_id: str,
    agent_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토너먼트 참가 신청. 에이전트 소유자만 참가 가능."""
    service = DebateTournamentService(db)
    try:
        entry = await service.join_tournament(tournament_id, agent_id, user)
    except ValueError as exc:
        detail = str(exc)
        if "DUPLICATE" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 참가 신청했습니다") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return {"ok": True, "seed": entry.seed}
