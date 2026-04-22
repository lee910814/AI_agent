import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog

logger = logging.getLogger(__name__)

# 사용자당 시간당 토큰 버스트 감지 임계값 — 초과 시 Sentry 경고 + error 로그
BURST_TOKENS_PER_HOUR_THRESHOLD = 100_000


class UsageService:
    """토큰 사용량 기록 및 집계 서비스.

    LLM 호출 토큰 수와 비용을 token_usage_logs 테이블에 기록하고,
    사용자별·관리자용 사용량 통계를 조회한다.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_usage(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID | None,
        llm_model_id: uuid.UUID,
        input_tokens: int,
        output_tokens: int,
    ) -> TokenUsageLog:
        """LLM 호출 토큰 사용량을 기록하고 비용을 산출하여 저장한다.

        llm_models 테이블에서 단가를 조회하여 입력/출력 토큰 비용을 계산한다.
        모델을 찾지 못하면 비용 0으로 기록한다.

        Args:
            user_id: 사용자 UUID.
            session_id: 토론 세션 UUID (선택). None이면 세션 외 호출.
            llm_model_id: llm_models 테이블의 모델 UUID.
            input_tokens: 입력 토큰 수.
            output_tokens: 출력 토큰 수.

        Returns:
            DB에 저장된 TokenUsageLog 인스턴스.
        """
        # 모델 비용 조회
        result = await self.db.execute(select(LLMModel).where(LLMModel.id == llm_model_id))
        model = result.scalar_one_or_none()

        if model:
            input_cost = Decimal(str(input_tokens)) * Decimal(str(model.input_cost_per_1m)) / Decimal("1000000")
            output_cost = Decimal(str(output_tokens)) * Decimal(str(model.output_cost_per_1m)) / Decimal("1000000")
            cost = input_cost + output_cost
        else:
            cost = Decimal("0")

        log = TokenUsageLog(
            user_id=user_id,
            session_id=session_id,
            llm_model_id=llm_model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)

        # 시간당 토큰 버스트 감지 — 비용 폭증 조기 경보 (실패해도 로그 기록은 유지)
        try:
            await self._check_burst_alert(user_id, input_tokens + output_tokens)
        except Exception:
            logger.debug("Burst check failed (non-critical)", exc_info=True)

        return log

    async def _check_burst_alert(self, user_id: uuid.UUID, just_used: int) -> None:
        """최근 1시간 토큰 합산이 임계값을 초과하면 Sentry 경고 + error 로그를 남긴다."""
        hour_ago = datetime.now(UTC) - timedelta(hours=1)
        result = await self.db.execute(
            select(func.sum(TokenUsageLog.input_tokens + TokenUsageLog.output_tokens)).where(
                TokenUsageLog.user_id == user_id,
                TokenUsageLog.created_at >= hour_ago,
            )
        )
        hourly_total = result.scalar() or 0
        if hourly_total >= BURST_TOKENS_PER_HOUR_THRESHOLD:
            from app.core.observability import capture_exception
            msg = (
                f"Token burst detected: user={user_id} used {hourly_total:,} tokens in the last hour "
                f"(threshold={BURST_TOKENS_PER_HOUR_THRESHOLD:,})"
            )
            logger.error(msg)
            capture_exception(RuntimeError(msg), user_id=str(user_id), hourly_total=hourly_total)

    async def get_user_summary(self, user_id: uuid.UUID) -> dict:
        """사용자 사용량 요약을 반환한다 (일/월/총계 + 모델별 분류).

        Args:
            user_id: 조회할 사용자 UUID.

        Returns:
            total_input_tokens, total_output_tokens, total_cost, daily_*, monthly_*, by_model 키를 포함하는 dict.
        """
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        base = select(
            func.coalesce(func.sum(TokenUsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(TokenUsageLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(TokenUsageLog.cost), 0).label("cost"),
        ).where(TokenUsageLog.user_id == user_id)

        # 총계
        total = (await self.db.execute(base)).one()
        # 오늘
        daily = (await self.db.execute(base.where(TokenUsageLog.created_at >= today_start))).one()
        # 이번 달
        monthly = (await self.db.execute(base.where(TokenUsageLog.created_at >= month_start))).one()

        # 모델별 사용량 — 전체/오늘/이번달 각각 조회
        # 전체 기간
        model_total_query = (
            select(
                LLMModel.id.label("model_id"),
                LLMModel.display_name,
                LLMModel.provider,
                LLMModel.tier,
                LLMModel.credit_per_1k_tokens,
                LLMModel.input_cost_per_1m,
                LLMModel.output_cost_per_1m,
                func.sum(TokenUsageLog.input_tokens).label("input_tokens"),
                func.sum(TokenUsageLog.output_tokens).label("output_tokens"),
                func.sum(TokenUsageLog.cost).label("cost"),
                func.count().label("request_count"),
            )
            .join(LLMModel, TokenUsageLog.llm_model_id == LLMModel.id)
            .where(TokenUsageLog.user_id == user_id)
            .group_by(
                LLMModel.id,
                LLMModel.display_name,
                LLMModel.provider,
                LLMModel.tier,
                LLMModel.credit_per_1k_tokens,
                LLMModel.input_cost_per_1m,
                LLMModel.output_cost_per_1m,
            )
            .order_by(func.sum(TokenUsageLog.cost).desc())
        )
        model_total_rows = (await self.db.execute(model_total_query)).all()

        # 오늘
        model_daily_agg = (
            select(
                TokenUsageLog.llm_model_id.label("model_id"),
                func.coalesce(func.sum(TokenUsageLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(TokenUsageLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(TokenUsageLog.cost), 0).label("cost"),
                func.count().label("request_count"),
            )
            .where(TokenUsageLog.user_id == user_id, TokenUsageLog.created_at >= today_start)
            .group_by(TokenUsageLog.llm_model_id)
        )
        daily_map = {str(r.model_id): r for r in (await self.db.execute(model_daily_agg)).all()}

        # 이번 달
        model_monthly_agg = (
            select(
                TokenUsageLog.llm_model_id.label("model_id"),
                func.coalesce(func.sum(TokenUsageLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(TokenUsageLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(TokenUsageLog.cost), 0).label("cost"),
                func.count().label("request_count"),
            )
            .where(TokenUsageLog.user_id == user_id, TokenUsageLog.created_at >= month_start)
            .group_by(TokenUsageLog.llm_model_id)
        )
        monthly_map = {str(r.model_id): r for r in (await self.db.execute(model_monthly_agg)).all()}

        by_model = []
        for row in model_total_rows:
            mid = str(row.model_id)
            d = daily_map.get(mid)
            m = monthly_map.get(mid)
            by_model.append(
                {
                    "model_name": row.display_name,
                    "provider": row.provider,
                    "tier": row.tier,
                    "credit_per_1k_tokens": int(row.credit_per_1k_tokens),
                    "input_cost_per_1m": float(row.input_cost_per_1m),
                    "output_cost_per_1m": float(row.output_cost_per_1m),
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                    "cost": float(row.cost),
                    "request_count": int(row.request_count),
                    "daily_input_tokens": int(d.input_tokens) if d else 0,
                    "daily_output_tokens": int(d.output_tokens) if d else 0,
                    "daily_cost": float(d.cost) if d else 0.0,
                    "daily_request_count": int(d.request_count) if d else 0,
                    "monthly_input_tokens": int(m.input_tokens) if m else 0,
                    "monthly_output_tokens": int(m.output_tokens) if m else 0,
                    "monthly_cost": float(m.cost) if m else 0.0,
                    "monthly_request_count": int(m.request_count) if m else 0,
                }
            )

        return {
            "total_input_tokens": int(total.input_tokens),
            "total_output_tokens": int(total.output_tokens),
            "total_cost": float(total.cost),
            "daily_input_tokens": int(daily.input_tokens),
            "daily_output_tokens": int(daily.output_tokens),
            "daily_cost": float(daily.cost),
            "monthly_input_tokens": int(monthly.input_tokens),
            "monthly_output_tokens": int(monthly.output_tokens),
            "monthly_cost": float(monthly.cost),
            "by_model": by_model,
        }

    async def get_user_history(self, user_id: uuid.UUID, days: int = 30) -> dict:
        """사용자의 일별 사용량 히스토리와 모델별 일별 분류를 반환한다.

        Args:
            user_id: 조회할 사용자 UUID.
            days: 조회 기간 (일 수). 기본값 30일.

        Returns:
            daily(일별 합산 목록), by_model_daily(모델별 일별 분류 목록) 키를 포함하는 dict.
        """
        since = datetime.now(UTC) - timedelta(days=days)

        # 일별 합산
        daily_query = (
            select(
                cast(TokenUsageLog.created_at, Date).label("date"),
                func.sum(TokenUsageLog.input_tokens).label("input_tokens"),
                func.sum(TokenUsageLog.output_tokens).label("output_tokens"),
                func.sum(TokenUsageLog.cost).label("cost"),
            )
            .where(
                TokenUsageLog.user_id == user_id,
                TokenUsageLog.created_at >= since,
            )
            .group_by(cast(TokenUsageLog.created_at, Date))
            .order_by(cast(TokenUsageLog.created_at, Date).asc())
        )
        daily_result = await self.db.execute(daily_query)
        daily_rows = daily_result.all()

        # 모델별 일별 분류
        model_daily_query = (
            select(
                cast(TokenUsageLog.created_at, Date).label("date"),
                LLMModel.display_name.label("model_name"),
                func.sum(TokenUsageLog.input_tokens).label("input_tokens"),
                func.sum(TokenUsageLog.output_tokens).label("output_tokens"),
                func.sum(TokenUsageLog.cost).label("cost"),
            )
            .join(LLMModel, TokenUsageLog.llm_model_id == LLMModel.id)
            .where(
                TokenUsageLog.user_id == user_id,
                TokenUsageLog.created_at >= since,
            )
            .group_by(cast(TokenUsageLog.created_at, Date), LLMModel.display_name)
            .order_by(cast(TokenUsageLog.created_at, Date).asc())
        )
        model_daily_result = await self.db.execute(model_daily_query)
        model_daily_rows = model_daily_result.all()

        return {
            "daily": [
                {
                    "date": str(row.date),
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                    "cost": float(row.cost),
                }
                for row in daily_rows
            ],
            "by_model_daily": [
                {
                    "date": str(row.date),
                    "model_name": row.model_name,
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                    "cost": float(row.cost),
                }
                for row in model_daily_rows
            ],
        }

    async def get_admin_summary(self) -> dict:
        """전체 사용자 사용량 통계를 반환한다 (관리자 전용).

        Returns:
            total, daily, monthly(각 input_tokens/output_tokens/cost/unique_users),
            by_model(모델별 비용 내림차순) 키를 포함하는 dict.
        """
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        base = select(
            func.coalesce(func.sum(TokenUsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(TokenUsageLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(TokenUsageLog.cost), 0).label("cost"),
            func.count(func.distinct(TokenUsageLog.user_id)).label("unique_users"),
        )

        # 총계
        total = (await self.db.execute(base)).one()
        # 오늘
        daily = (await self.db.execute(base.where(TokenUsageLog.created_at >= today_start))).one()
        # 이번 달
        monthly = (await self.db.execute(base.where(TokenUsageLog.created_at >= month_start))).one()

        # 모델별 사용량
        model_query = (
            select(
                LLMModel.display_name,
                func.sum(TokenUsageLog.input_tokens).label("input_tokens"),
                func.sum(TokenUsageLog.output_tokens).label("output_tokens"),
                func.sum(TokenUsageLog.cost).label("cost"),
            )
            .join(LLMModel, TokenUsageLog.llm_model_id == LLMModel.id)
            .group_by(LLMModel.display_name)
            .order_by(func.sum(TokenUsageLog.cost).desc())
        )
        model_rows = (await self.db.execute(model_query)).all()

        return {
            "total": {
                "input_tokens": int(total.input_tokens),
                "output_tokens": int(total.output_tokens),
                "cost": float(total.cost),
                "unique_users": int(total.unique_users),
            },
            "daily": {
                "input_tokens": int(daily.input_tokens),
                "output_tokens": int(daily.output_tokens),
                "cost": float(daily.cost),
                "unique_users": int(daily.unique_users),
            },
            "monthly": {
                "input_tokens": int(monthly.input_tokens),
                "output_tokens": int(monthly.output_tokens),
                "cost": float(monthly.cost),
                "unique_users": int(monthly.unique_users),
            },
            "by_model": [
                {
                    "model_name": row.display_name,
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                    "cost": float(row.cost),
                }
                for row in model_rows
            ],
        }

    async def get_user_usage_admin(self, user_id: uuid.UUID) -> dict:
        """관리자가 특정 사용자의 사용량 요약 및 30일 히스토리를 조회한다.

        Args:
            user_id: 조회할 사용자 UUID.

        Returns:
            summary(get_user_summary 결과), history(get_user_history 결과) 키를 포함하는 dict.
        """
        summary = await self.get_user_summary(user_id)
        history = await self.get_user_history(user_id, days=30)
        return {"summary": summary, "history": history}
