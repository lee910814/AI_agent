"""관리자 사용자 관리 API — 목록 조회, 역할 변경, 일괄 삭제."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.debate_agent import DebateAgent
from app.models.user import User
from app.schemas.user import (
    AdminUserDetailResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    UserResponse,
    UserStats,
)

router = APIRouter()


class UserListResponse(BaseModel):
    """사용자 목록 응답 스키마."""

    items: list[UserResponse]
    total: int
    stats: UserStats | None = None


class RoleUpdate(BaseModel):
    """사용자 역할 변경 요청 스키마."""

    role: str


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=50),
    role: str | None = Query(None),
    age_group: str | None = Query(None),
    sort_by: str | None = Query(None, description="정렬 기준: created_at(기본) | credit_balance | nickname"),
    has_agents: bool | None = Query(None, description="토론 에이전트 보유 여부 필터"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 목록 (서버사이드 검색/필터 + 통계).

    sort_by: created_at(기본)|credit_balance|nickname, has_agents: 에이전트 보유 여부 필터.
    """
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if search:
        search_filter = or_(User.login_id.ilike(f"%{search}%"), User.nickname.ilike(f"%{search}%"))
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if age_group:
        query = query.where(User.age_group == age_group)
        count_query = count_query.where(User.age_group == age_group)
    if has_agents is not None:
        agent_subquery = select(DebateAgent.owner_id).distinct().subquery()
        if has_agents:
            query = query.where(User.id.in_(select(agent_subquery.c.owner_id)))
            count_query = count_query.where(User.id.in_(select(agent_subquery.c.owner_id)))
        else:
            query = query.where(User.id.not_in(select(agent_subquery.c.owner_id)))
            count_query = count_query.where(User.id.not_in(select(agent_subquery.c.owner_id)))

    if sort_by == "credit_balance":
        order_col = User.credit_balance.desc()
    elif sort_by == "nickname":
        order_col = User.nickname.asc()
    else:
        order_col = User.created_at.desc()

    total = (await db.execute(count_query)).scalar()
    result = await db.execute(query.order_by(order_col).offset(skip).limit(limit))
    items = result.scalars().all()

    stats_result = await db.execute(
        select(
            func.count().label("total_users"),
            func.count().filter(User.role == "superadmin").label("superadmin_count"),
            func.count().filter(User.role == "admin").label("admin_count"),
            func.count().filter(User.age_group == "adult_verified").label("adult_verified_count"),
            func.count().filter(User.age_group == "unverified").label("unverified_count"),
            func.count().filter(User.age_group == "minor_safe").label("minor_safe_count"),
        ).select_from(User)
    )
    row = stats_result.one()
    stats = UserStats(
        total_users=row.total_users,
        superadmin_count=row.superadmin_count,
        admin_count=row.admin_count,
        adult_verified_count=row.adult_verified_count,
        unverified_count=row.unverified_count,
        minor_safe_count=row.minor_safe_count,
    )

    return {"items": list(items), "total": total, "stats": stats}


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_users(
    data: BulkDeleteRequest,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 일괄 삭제. 관리자 계정은 삭제 불가."""
    if not data.user_ids:
        return BulkDeleteResponse(deleted_count=0, skipped_admin_ids=[])

    target_ids = [uid for uid in data.user_ids if uid != admin.id]

    admin_result = await db.execute(
        select(User.id).where(User.id.in_(target_ids), User.role.in_(("admin", "superadmin")))
    )
    admin_ids = [row[0] for row in admin_result.all()]
    skipped = [uid for uid in data.user_ids if uid == admin.id] + admin_ids

    delete_ids = [uid for uid in target_ids if uid not in admin_ids]
    if not delete_ids:
        return BulkDeleteResponse(deleted_count=0, skipped_admin_ids=skipped)

    result = await db.execute(delete(User).where(User.id.in_(delete_ids)))
    await db.commit()

    return BulkDeleteResponse(
        deleted_count=result.rowcount,
        skipped_admin_ids=skipped,
    )


@router.get("/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 상세 정보."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return AdminUserDetailResponse(
        id=user.id,
        login_id=user.login_id,
        nickname=user.nickname,
        role=user.role,
        age_group=user.age_group,
        adult_verified_at=user.adult_verified_at,
        preferred_llm_model_id=user.preferred_llm_model_id,
        preferred_themes=user.preferred_themes,
        credit_balance=user.credit_balance,
        last_credit_grant_at=user.last_credit_grant_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        session_count=0,
        message_count=0,
        subscription_status=None,
    )


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    data: RoleUpdate,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """사용자 역할 변경 (superadmin 전용)."""
    if data.role not in ("user", "admin", "superadmin"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = data.role
    await db.commit()
    await db.refresh(user)
    return user
