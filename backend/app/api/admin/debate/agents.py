"""관리자 토론 에이전트 관리."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.debate_agent import DebateAgent, DebateAgentVersion
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.user import User

router = APIRouter()


@router.get("/agents")
async def list_all_debate_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    provider: str | None = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 토론 에이전트 목록 (관리자)."""
    count_query = select(func.count(DebateAgent.id)).join(User, DebateAgent.owner_id == User.id)
    main_query = (
        select(DebateAgent, User.nickname)
        .join(User, DebateAgent.owner_id == User.id)
        .order_by(DebateAgent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if search:
        like = f"%{search}%"
        count_query = count_query.where((DebateAgent.name.ilike(like)) | (User.nickname.ilike(like)))
        main_query = main_query.where((DebateAgent.name.ilike(like)) | (User.nickname.ilike(like)))
    if provider:
        count_query = count_query.where(DebateAgent.provider == provider)
        main_query = main_query.where(DebateAgent.provider == provider)

    total = (await db.execute(count_query)).scalar() or 0
    rows = (await db.execute(main_query)).all()

    return {
        "items": [
            {
                "id": str(agent.id),
                "name": agent.name,
                "provider": agent.provider,
                "model_id": agent.model_id,
                "elo_rating": agent.elo_rating,
                "image_url": agent.image_url,
                "owner_id": str(agent.owner_id),
                "owner_nickname": nickname,
                "wins": agent.wins,
                "losses": agent.losses,
                "draws": agent.draws,
                "is_active": agent.is_active,
                "tier": agent.tier,
                "is_profile_public": agent.is_profile_public,
                "created_at": agent.created_at,
            }
            for agent, nickname in rows
        ],
        "total": total,
    }


@router.get("/agents/{agent_id}")
async def get_debate_agent_detail(
    agent_id: str,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 상세 조회 (superadmin 전용). 시스템 프롬프트 포함 버전 히스토리 + 최근 매치 5건."""
    agent = await db.get(DebateAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    owner = await db.get(User, agent.owner_id)
    owner_agent_count = (await db.execute(
        select(func.count(DebateAgent.id)).where(DebateAgent.owner_id == agent.owner_id)
    )).scalar() or 0

    versions = (
        await db.execute(
            select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent.id)
            .order_by(DebateAgentVersion.version_number.desc())
        )
    ).scalars().all()

    recent_matches = [
        {
            "id": str(m.id),
            "topic_title": title,
            "status": m.status,
            "winner_id": str(m.winner_id) if m.winner_id else None,
            "score_a": m.score_a,
            "score_b": m.score_b,
            "created_at": m.created_at,
        }
        for m, title in (
            await db.execute(
                select(DebateMatch, DebateTopic.title)
                .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
                .where((DebateMatch.agent_a_id == agent.id) | (DebateMatch.agent_b_id == agent.id))
                .order_by(DebateMatch.created_at.desc())
                .limit(5)
            )
        ).all()
    ]

    return {
        "id": str(agent.id),
        "name": agent.name,
        "description": agent.description,
        "provider": agent.provider,
        "model_id": agent.model_id,
        "image_url": agent.image_url,
        "elo_rating": agent.elo_rating,
        "tier": agent.tier,
        "wins": agent.wins,
        "losses": agent.losses,
        "draws": agent.draws,
        "is_active": agent.is_active,
        "is_platform": agent.is_platform,
        "is_profile_public": agent.is_profile_public,
        "is_system_prompt_public": agent.is_system_prompt_public,
        "created_at": agent.created_at,
        "owner": {
            "id": str(owner.id) if owner else None,
            "nickname": owner.nickname if owner else "[삭제됨]",
            "created_at": owner.created_at if owner else None,
            "agent_count": owner_agent_count,
        },
        "versions": [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "version_tag": v.version_tag,
                "system_prompt": v.system_prompt,
                "parameters": v.parameters,
                "wins": v.wins,
                "losses": v.losses,
                "draws": v.draws,
                "created_at": v.created_at,
            }
            for v in versions
        ],
        "recent_matches": recent_matches,
    }


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_debate_agent(
    agent_id: str,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """토론 에이전트 강제 삭제 (superadmin 전용, 진행 중인 매치 있으면 불가)."""
    agent = await db.get(DebateAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    active_count = (
        await db.execute(
            select(func.count(DebateMatch.id)).where(
                ((DebateMatch.agent_a_id == agent.id) | (DebateMatch.agent_b_id == agent.id))
                & DebateMatch.status.in_(["pending", "in_progress", "waiting_agent"])
            )
        )
    ).scalar() or 0

    if active_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="진행 중인 매치가 있어 삭제할 수 없습니다.",
        )

    await db.delete(agent)
    await db.commit()
