"""관리자 시즌 관리."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_superadmin
from app.models.debate_season import DebateSeason
from app.models.user import User
from app.schemas.debate_season import SeasonCreate
from app.services.debate.season_service import DebateSeasonService

router = APIRouter()


@router.post("/seasons", status_code=status.HTTP_201_CREATED)
async def create_season(
    data: SeasonCreate,
    user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """시즌 생성 (superadmin 전용)."""
    service = DebateSeasonService(db)
    season = await service.create_season(
        season_number=data.season_number,
        title=data.title,
        start_at=data.start_at,
        end_at=data.end_at,
    )
    return {"id": str(season.id), "status": season.status}


@router.get("/seasons")
async def list_seasons(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """전체 시즌 목록 조회 (superadmin 전용)."""
    total = (await db.execute(select(func.count(DebateSeason.id)))).scalar() or 0
    seasons = (
        await db.execute(
            select(DebateSeason)
            .order_by(DebateSeason.season_number.desc())
            .offset(skip)
            .limit(limit)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": str(s.id),
                "season_number": s.season_number,
                "title": s.title,
                "start_at": s.start_at.isoformat(),
                "end_at": s.end_at.isoformat(),
                "status": s.status,
            }
            for s in seasons
        ],
        "total": total,
    }


@router.post("/seasons/{season_id}/activate")
async def activate_season(
    season_id: str,
    user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """시즌 활성화 — upcoming → active (superadmin 전용)."""
    existing = await db.execute(
        select(DebateSeason).where(DebateSeason.status == "active")
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 활성 시즌이 존재합니다. 먼저 현재 시즌을 종료하세요.",
        )

    season = (
        await db.execute(select(DebateSeason).where(DebateSeason.id == uuid.UUID(season_id)))
    ).scalar_one_or_none()
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="시즌을 찾을 수 없습니다")
    if season.status != "upcoming":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="upcoming 상태의 시즌만 활성화할 수 있습니다",
        )
    season.status = "active"
    await db.commit()
    return {"ok": True}


@router.post("/seasons/{season_id}/close")
async def close_season(
    season_id: str,
    user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """시즌 종료 (superadmin 전용)."""
    service = DebateSeasonService(db)
    try:
        await service.close_season(season_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_season(
    season_id: str,
    user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """시즌 삭제 — upcoming 상태만 가능 (superadmin 전용)."""
    season = (
        await db.execute(select(DebateSeason).where(DebateSeason.id == uuid.UUID(season_id)))
    ).scalar_one_or_none()
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="시즌을 찾을 수 없습니다")
    if season.status != "upcoming":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="upcoming 상태의 시즌만 삭제할 수 있습니다",
        )
    await db.delete(season)
    await db.commit()
