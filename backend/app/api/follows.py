"""팔로우 API 라우터 — 팔로우/언팔로우, 팔로우 목록 조회, 상태 확인."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, get_db
from app.core.deps import get_current_user
from app.models.debate_agent import DebateAgent
from app.models.user import User
from app.schemas.follow import FollowCreate, FollowListResponse, FollowResponse
from app.services.follow_service import FollowService

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_follow_response(follow, target_name: str, target_image_url: str | None) -> FollowResponse:
    """UserFollow 객체와 조회된 대상 정보를 FollowResponse로 조립.

    Args:
        follow: UserFollow ORM 모델 인스턴스.
        target_name: 팔로우 대상의 이름(닉네임 또는 에이전트명).
        target_image_url: 팔로우 대상의 이미지 URL (없으면 None).

    Returns:
        FollowResponse — 클라이언트에 반환할 팔로우 응답 스키마.
    """
    return FollowResponse(
        id=follow.id,
        target_type=follow.target_type,
        target_id=follow.target_id,
        target_name=target_name,
        target_image_url=target_image_url,
        created_at=follow.created_at,
    )


@router.post("", response_model=FollowResponse, status_code=status.HTTP_201_CREATED)
async def follow_target(
    data: FollowCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """팔로우 생성. 중복 시 409, 대상 미존재 시 404, 자기 자신 팔로우 시 400."""
    svc = FollowService(db)
    try:
        follow = await svc.follow(current_user.id, data.target_type, data.target_id)
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        if detail == "already_following":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 팔로우 중입니다") from exc
        if detail == "target_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대상을 찾을 수 없습니다") from exc
        if detail == "self_follow":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="자기 자신을 팔로우할 수 없습니다"
            ) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    # 신규 팔로워 알림 — 별도 세션으로 실행해 팔로우 세션 오염 방지
    try:
        from app.services.notification_service import NotificationService
        async with async_session() as notify_db:
            await NotificationService(notify_db).notify_new_follower(
                follower_id=current_user.id,
                target_type=data.target_type,
                target_id=data.target_id,
            )
            await notify_db.commit()
    except Exception:
        logger.warning(
            "notify_new_follower failed: follower=%s target=%s/%s",
            current_user.id,
            data.target_type,
            data.target_id,
        )

    # 에이전트 팔로우 시 커뮤니티 참여점수 비동기 업데이트
    if data.target_type == "agent":
        from app.services.community_service import _schedule_stats_update
        _schedule_stats_update(str(current_user.id), follows_delta=1)

    # 응답 조립을 위해 대상 이름·이미지 조회
    if data.target_type == "agent":
        agent = await db.get(DebateAgent, data.target_id)
        name = agent.name if agent else "(삭제된 에이전트)"
        image_url = agent.image_url if agent else None
    else:
        user = await db.get(User, data.target_id)
        name = user.nickname if user else "(삭제된 사용자)"
        image_url = None

    return _build_follow_response(follow, name, image_url)


@router.delete("/{target_type}/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_target(
    target_type: str,
    target_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """언팔로우. 팔로우 관계가 없으면 404."""
    if target_type not in ("user", "agent"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 target_type입니다")

    svc = FollowService(db)
    try:
        await svc.unfollow(current_user.id, target_type, target_id)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="팔로우 관계를 찾을 수 없습니다") from exc

    # 에이전트 언팔로우 시 커뮤니티 참여점수 비동기 업데이트
    if target_type == "agent":
        from app.services.community_service import _schedule_stats_update
        _schedule_stats_update(str(current_user.id), follows_delta=-1)


@router.get("/following", response_model=FollowListResponse)
async def get_following(
    target_type: str | None = Query(None, description="user 또는 agent 필터"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 팔로우 목록 조회. target_type으로 필터링 가능."""
    if target_type is not None and target_type not in ("user", "agent"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 target_type입니다")

    svc = FollowService(db)
    follows, total = await svc.get_following(
        user_id=current_user.id,
        target_type=target_type,
        offset=offset,
        limit=limit,
    )

    # 에이전트 ID와 사용자 ID를 분리하여 배치 조회 — N+1 방지
    agent_ids = [f.target_id for f in follows if f.target_type == "agent"]
    user_ids = [f.target_id for f in follows if f.target_type == "user"]

    agents_map: dict[UUID, DebateAgent] = {}
    users_map: dict[UUID, User] = {}

    if agent_ids:
        res = await db.execute(select(DebateAgent).where(DebateAgent.id.in_(agent_ids)))
        agents_map = {a.id: a for a in res.scalars().all()}

    if user_ids:
        res = await db.execute(select(User).where(User.id.in_(user_ids)))
        users_map = {u.id: u for u in res.scalars().all()}

    items = []
    for follow in follows:
        if follow.target_type == "agent":
            agent = agents_map.get(follow.target_id)
            name = agent.name if agent else "(삭제된 에이전트)"
            image_url = agent.image_url if agent else None
        else:
            user = users_map.get(follow.target_id)
            name = user.nickname if user else "(삭제된 사용자)"
            image_url = None
        items.append(_build_follow_response(follow, name, image_url))

    return FollowListResponse(items=items, total=total)


@router.get("/status")
async def get_follow_status(
    target_type: str = Query(..., description="user 또는 agent"),
    target_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """팔로우 상태 및 팔로워 수 조회."""
    if target_type not in ("user", "agent"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 target_type입니다")

    svc = FollowService(db)
    is_following = await svc.is_following(current_user.id, target_type, target_id)
    follower_count = await svc.get_follower_count(target_type, target_id)
    return {"is_following": is_following, "follower_count": follower_count}
