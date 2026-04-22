"""LLM 모델 API 라우터 — 사용 가능한 모델 목록 조회, 선호 모델 설정."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.debate_agent import DebateAgent
from app.models.llm_model import LLMModel
from app.models.user import User
from app.schemas.llm_model import LLMModelResponse, LLMModelStatsResponse

router = APIRouter()


class PreferredModelRequest(BaseModel):
    """선호 LLM 모델 변경 요청 스키마."""

    model_id: uuid.UUID


@router.get("", response_model=list[LLMModelResponse])
async def list_available_models(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용 가능한 LLM 모델 목록. 활성 모델만, 성인전용 모델은 성인인증 사용자에게만 노출."""
    query = select(LLMModel).where(LLMModel.is_active.is_(True))

    if user.adult_verified_at is None:
        query = query.where(LLMModel.is_adult_only.is_(False))

    result = await db.execute(query.order_by(LLMModel.display_name))
    return list(result.scalars().all())


@router.get("/stats", response_model=list[LLMModelStatsResponse])
async def get_model_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """활성 LLM 모델별 사용 에이전트 수와 누적 전적·승률 통계."""
    rows = await db.execute(
        select(
            LLMModel.id,
            LLMModel.model_id,
            LLMModel.display_name,
            LLMModel.provider,
            LLMModel.tier,
            LLMModel.input_cost_per_1m,
            LLMModel.output_cost_per_1m,
            LLMModel.max_context_length,
            func.count(DebateAgent.id).label("agent_count"),
            func.coalesce(func.sum(DebateAgent.wins), 0).label("total_wins"),
            func.coalesce(func.sum(DebateAgent.losses), 0).label("total_losses"),
            func.coalesce(func.sum(DebateAgent.draws), 0).label("total_draws"),
        )
        .outerjoin(DebateAgent, DebateAgent.model_id == LLMModel.model_id)
        .where(LLMModel.is_active.is_(True))
        .group_by(
            LLMModel.id,
            LLMModel.model_id,
            LLMModel.display_name,
            LLMModel.provider,
            LLMModel.tier,
            LLMModel.input_cost_per_1m,
            LLMModel.output_cost_per_1m,
            LLMModel.max_context_length,
        )
        .order_by(LLMModel.display_name)
    )

    stats = []
    for row in rows:
        total_decided = row.total_wins + row.total_losses
        win_rate = row.total_wins / total_decided if total_decided > 0 else None
        stats.append(
            LLMModelStatsResponse(
                id=row.id,
                model_id=row.model_id,
                display_name=row.display_name,
                provider=row.provider,
                tier=row.tier,
                input_cost_per_1m=float(row.input_cost_per_1m),
                output_cost_per_1m=float(row.output_cost_per_1m),
                max_context_length=row.max_context_length,
                agent_count=row.agent_count,
                total_wins=row.total_wins,
                total_losses=row.total_losses,
                total_draws=row.total_draws,
                win_rate=win_rate,
            )
        )
    return stats


@router.put("/preferred", response_model=LLMModelResponse)
async def set_preferred_model(
    data: PreferredModelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """선호 LLM 모델 변경."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == data.model_id))
    model = result.scalar_one_or_none()

    if model is None or not model.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found or inactive",
        )

    # 성인전용 모델은 성인인증 필요
    if model.is_adult_only and user.adult_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adult verification required for this model",
        )

    user.preferred_llm_model_id = model.id
    await db.commit()
    return model
