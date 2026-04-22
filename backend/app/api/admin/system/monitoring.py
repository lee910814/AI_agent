"""관리자 모니터링 API — 시스템 통계, 토큰 사용 로그 조회."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.models.user import User

router = APIRouter()


@router.get("/stats")
async def get_system_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """시스템 통계 (사용자수, 토큰 사용량)."""
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar()
    total_agents = (await db.execute(select(func.count()).select_from(DebateAgent))).scalar()
    total_matches = (await db.execute(select(func.count()).select_from(DebateMatch))).scalar()
    new_users_week = (
        await db.execute(select(func.count()).select_from(User).where(User.created_at >= week_ago))
    ).scalar()

    return {
        "totals": {
            "users": total_users,
            "agents": total_agents,
            "matches": total_matches,
        },
        "weekly": {
            "new_users": new_users_week,
        },
    }


@router.get("/logs")
async def get_activity_logs(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=200),
):
    """최근 토큰 사용 로그 (사용자 닉네임, 모델명 JOIN)."""
    since = datetime.now(UTC) - timedelta(days=days)

    usage_query = (
        select(
            TokenUsageLog.id,
            TokenUsageLog.user_id,
            TokenUsageLog.session_id,
            TokenUsageLog.match_id,
            TokenUsageLog.llm_model_id,
            TokenUsageLog.input_tokens,
            TokenUsageLog.output_tokens,
            TokenUsageLog.cost,
            TokenUsageLog.created_at,
            User.nickname.label("user_nickname"),
            LLMModel.display_name.label("model_name"),
            LLMModel.provider.label("model_provider"),
            DebateTopic.title.label("topic_title"),
        )
        .join(User, TokenUsageLog.user_id == User.id)
        .outerjoin(LLMModel, TokenUsageLog.llm_model_id == LLMModel.id)
        .outerjoin(DebateMatch, TokenUsageLog.match_id == DebateMatch.id)
        .outerjoin(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
        .where(TokenUsageLog.created_at >= since)
        .order_by(TokenUsageLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(usage_query)
    logs = result.all()

    return {
        "logs": [
            {
                "id": log.id,
                "user_id": str(log.user_id),
                "user_nickname": log.user_nickname or str(log.user_id)[:8],
                "session_id": str(log.session_id) if log.session_id else None,
                "match_id": str(log.match_id) if log.match_id else None,
                "topic_title": log.topic_title,
                "llm_model_id": str(log.llm_model_id) if log.llm_model_id else None,
                "model_name": log.model_name,
                "model_provider": log.model_provider,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.input_tokens + log.output_tokens,
                "cost": float(log.cost),
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "period_days": days,
        "total_returned": len(logs),
    }


@router.get("/logs/{log_id}")
async def get_log_detail(
    log_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """로그 상세 — 해당 LLM 호출 정보."""
    detail_query = (
        select(
            TokenUsageLog,
            DebateTopic.title.label("topic_title"),
        )
        .outerjoin(DebateMatch, TokenUsageLog.match_id == DebateMatch.id)
        .outerjoin(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
        .where(TokenUsageLog.id == log_id)
    )
    detail_result = await db.execute(detail_query)
    row = detail_result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")

    log, topic_title = row

    return {
        "id": log.id,
        "input_tokens": log.input_tokens,
        "output_tokens": log.output_tokens,
        "total_tokens": log.input_tokens + log.output_tokens,
        "cost": float(log.cost),
        "created_at": log.created_at.isoformat(),
        "session_id": str(log.session_id) if log.session_id else None,
        "match_id": str(log.match_id) if log.match_id else None,
        "topic_title": topic_title,
    }
