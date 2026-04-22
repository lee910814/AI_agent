"""알림 API 라우터 — 알림 목록 조회, 읽음 처리, 미읽기 수 조회."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter()


@router.put("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """전체 알림 읽음 처리."""
    svc = NotificationService(db)
    updated = await svc.mark_all_read(current_user.id)
    await db.commit()
    return {"updated": updated}


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """알림 목록 조회."""
    svc = NotificationService(db)
    notifications, total, unread_count = await svc.get_list(
        user_id=current_user.id,
        offset=offset,
        limit=limit,
        unread_only=unread_only,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """미읽기 알림 수 조회."""
    svc = NotificationService(db)
    count = await svc.get_unread_count(current_user.id)
    return {"count": count}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """단건 알림 읽음 처리."""
    svc = NotificationService(db)
    try:
        await svc.mark_read(notification_id, current_user.id)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="알림을 찾을 수 없습니다") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="접근 권한이 없습니다") from exc
    return {"ok": True}
