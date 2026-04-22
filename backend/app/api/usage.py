"""토큰 사용량 API 라우터 — 내 사용량 요약 및 이력 조회."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.usage import UsageHistoryResponse, UsageSummary
from app.services.usage_service import UsageService

router = APIRouter()


@router.get("/me", response_model=UsageSummary)
async def get_my_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 토큰 사용량 요약 (일/월/총계)."""
    service = UsageService(db)
    return await service.get_user_summary(user.id)


@router.get("/me/history", response_model=UsageHistoryResponse)
async def get_my_usage_history(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """일별 사용량 히스토리 (차트용)."""
    service = UsageService(db)
    return await service.get_user_history(user.id, days=days)
