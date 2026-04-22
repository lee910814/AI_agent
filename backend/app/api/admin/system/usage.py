"""관리자 사용량 조회 API — 전체 사용량 통계, 사용자 검색, 쿼터 관리."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.services.usage_service import UsageService

router = APIRouter()


class UserSearchResult(BaseModel):
    """사용자 검색 결과 스키마."""

    id: uuid.UUID
    nickname: str
    login_id: str


@router.get("/summary")
async def get_usage_summary(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 사용량 통계."""
    service = UsageService(db)
    return await service.get_admin_summary()


@router.get("/users/{user_id}")
async def get_user_usage(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """특정 사용자 상세 사용량."""
    service = UsageService(db)
    return await service.get_user_usage_admin(user_id)


@router.get("/user-search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(..., min_length=1, max_length=50),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """닉네임/로그인ID로 사용자 검색."""
    result = await db.execute(
        select(User.id, User.nickname, User.login_id)
        .where(
            or_(
                User.nickname.ilike(f"%{q}%"),
                User.login_id.ilike(f"%{q}%"),
            )
        )
        .limit(10)
    )
    rows = result.all()
    return [UserSearchResult(id=r.id, nickname=r.nickname, login_id=r.login_id) for r in rows]


@router.get("/quotas")
async def list_quotas(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """커스텀 쿼터가 설정된 사용자 목록."""
    result = await db.execute(
        select(User.id, User.nickname, User.daily_token_limit, User.monthly_token_limit)
        .where(
            or_(
                User.daily_token_limit.is_not(None),
                User.monthly_token_limit.is_not(None),
            )
        )
        .order_by(User.nickname)
    )
    rows = result.all()
    return [
        {
            "user_id": str(r.id),
            "nickname": r.nickname,
            "daily_token_limit": r.daily_token_limit,
            "monthly_token_limit": r.monthly_token_limit,
        }
        for r in rows
    ]


@router.get("/quotas/{user_id}")
async def get_quota(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """특정 사용자 쿼터 조회. 미설정 시 null 반환."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.daily_token_limit is None and user.monthly_token_limit is None:
        return None
    return {
        "user_id": str(user.id),
        "nickname": user.nickname,
        "daily_token_limit": user.daily_token_limit,
        "monthly_token_limit": user.monthly_token_limit,
    }


@router.put("/quotas/{user_id}")
async def upsert_quota(
    user_id: uuid.UUID,
    body: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 쿼터 설정 (upsert)."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.daily_token_limit = body.get("daily_token_limit")
    user.monthly_token_limit = body.get("monthly_token_limit")
    await db.commit()
    await db.refresh(user)
    return {
        "user_id": str(user.id),
        "nickname": user.nickname,
        "daily_token_limit": user.daily_token_limit,
        "monthly_token_limit": user.monthly_token_limit,
    }
