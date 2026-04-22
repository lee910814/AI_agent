"""매치 조회, 하이라이트, 예측투표 정산, 요약 리포트 생성 서비스."""

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog

logger = logging.getLogger(__name__)


def calculate_token_cost(tokens: int, cost_per_1m: Decimal) -> Decimal:
    """토큰 수와 백만 토큰당 비용으로 실제 비용을 계산한다.

    Args:
        tokens: 사용된 토큰 수.
        cost_per_1m: 백만 토큰당 비용 (Decimal).

    Returns:
        실제 비용 (Decimal).
    """
    return Decimal(str(tokens)) * cost_per_1m / Decimal("1000000")



def _extract_json_from_response(content: str) -> dict:
    """LLM 응답에서 JSON을 추출한다.
    
    마크다운 코드블록으로 감싸져 있거나 순수 JSON일 수 있으므로
    유효한 JSON을 추출하려고 시도한다.
    
    Args:
        content: LLM 응답 텍스트.
        
    Returns:
        파싱된 JSON 딕셔너리.
        
    Raises:
        json.JSONDecodeError: JSON 파싱 실패 시.
    """
    # 마크다운 코드블록 제거 (```json ... ``` 또는 ``` ... ```)
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if match:
        content = match.group(1).strip()
    
    # JSON 파싱
    return json.loads(content)


class DebateMatchService:
    """매치 조회, 예측투표 생성·정산, 하이라이트, 요약 상태 관리 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_match(self, match_id: str) -> dict | None:
        """매치 상세 조회. 에이전트 요약 포함."""
        result = await self.db.execute(
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .where(DebateMatch.id == match_id)
        )
        row = result.one_or_none()
        if row is None:
            return None

        match, topic_title = row

        # N+1 방지: 두 에이전트를 단일 배치 쿼리로 조회 후 기존 _agent_from_map 재사용
        agent_ids = {match.agent_a_id, match.agent_b_id}
        agents_res = await self.db.execute(select(DebateAgent).where(DebateAgent.id.in_(agent_ids)))
        agents_map = {str(a.id): a for a in agents_res.scalars()}
        agent_a = self._agent_from_map(agents_map, match.agent_a_id)
        agent_b = self._agent_from_map(agents_map, match.agent_b_id)

        turn_count_result = await self.db.execute(
            select(func.count(DebateTurnLog.id)).where(DebateTurnLog.match_id == match.id)
        )
        turn_count = turn_count_result.scalar() or 0

        return {
            "id": str(match.id),
            "topic_id": str(match.topic_id),
            "topic_title": topic_title,
            "agent_a": agent_a,
            "agent_b": agent_b,
            "status": match.status,
            "winner_id": str(match.winner_id) if match.winner_id else None,
            "score_a": match.score_a,
            "score_b": match.score_b,
            "penalty_a": match.penalty_a,
            "penalty_b": match.penalty_b,
            "elo_a_before": match.elo_a_before,
            "elo_b_before": match.elo_b_before,
            "elo_a_after": match.elo_a_after,
            "elo_b_after": match.elo_b_after,
            "match_type": match.match_type,
            "series_id": str(match.series_id) if match.series_id else None,
            "turn_count": turn_count,
            "started_at": match.started_at,
            "finished_at": match.finished_at,
            "created_at": match.created_at,
        }

    async def get_match_turns(self, match_id: str) -> list[DebateTurnLog]:
        """매치의 모든 턴 로그를 턴 번호·발언자 순으로 반환.

        Args:
            match_id: 매치 UUID 문자열.

        Returns:
            DebateTurnLog 목록.
        """
        result = await self.db.execute(
            select(DebateTurnLog)
            .where(DebateTurnLog.match_id == match_id)
            .order_by(DebateTurnLog.turn_number, DebateTurnLog.speaker)
        )
        return list(result.scalars().all())

    async def get_scorecard(self, match_id: str) -> dict | None:
        """매치 스코어카드 조회.

        Args:
            match_id: 매치 UUID 문자열.

        Returns:
            scorecard 데이터에 winner_id, result 필드를 추가한 dict.
            매치가 없거나 scorecard가 없으면 None.
        """
        result = await self.db.execute(
            select(DebateMatch).where(DebateMatch.id == match_id)
        )
        match = result.scalar_one_or_none()
        if match is None or match.scorecard is None:
            return None
        return {
            **match.scorecard,
            "winner_id": str(match.winner_id) if match.winner_id else None,
            "result": "draw" if match.winner_id is None and match.status == "completed" else (
                "win" if match.winner_id else "pending"
            ),
        }

    async def list_matches(
        self,
        topic_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 20,
        search: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        include_test: bool = False,
    ) -> tuple[list[dict], int]:
        query = (
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .join(DebateAgent, DebateMatch.agent_a_id == DebateAgent.id, isouter=True)
        )
        count_query = (
            select(func.count(DebateMatch.id))
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .join(DebateAgent, DebateMatch.agent_a_id == DebateAgent.id, isouter=True)
        )
        if not include_test:
            # 테스트 매치(관리자 강제매치)는 일반 목록에서 제외 — ELO 미반영
            query = query.where(DebateMatch.is_test.is_(False))
            count_query = count_query.where(DebateMatch.is_test.is_(False))

        if topic_id:
            query = query.where(DebateMatch.topic_id == topic_id)
            count_query = count_query.where(DebateMatch.topic_id == topic_id)
        if agent_id:
            query = query.where(
                (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id)
            )
            count_query = count_query.where(
                (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id)
            )
        if status:
            query = query.where(DebateMatch.status == status)
            count_query = count_query.where(DebateMatch.status == status)
        if search:
            # 에이전트명(A측) 또는 토픽 제목으로 검색
            # % _ \ 이스케이프 — SQL LIKE 패턴 문자로 오해석 방지
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{escaped}%"
            search_cond = (DebateAgent.name.ilike(like)) | (DebateTopic.title.ilike(like))
            query = query.where(search_cond)
            count_query = count_query.where(search_cond)
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                query = query.where(DebateMatch.created_at >= dt_from)
                count_query = count_query.where(DebateMatch.created_at >= dt_from)
            except ValueError:
                logger.warning("list_matches: invalid date_from=%s, skipping", date_from)
        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to)
                query = query.where(DebateMatch.created_at <= dt_to)
                count_query = count_query.where(DebateMatch.created_at <= dt_to)
            except ValueError:
                logger.warning("list_matches: invalid date_to=%s, skipping", date_to)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.db.execute(
            query.order_by(DebateMatch.created_at.desc()).offset(skip).limit(limit)
        )
        rows = result.all()

        # N+1 방지: 페이지 내 모든 에이전트 ID를 단일 배치 쿼리로 조회
        agent_ids = {
            id_
            for match, _ in rows
            for id_ in (match.agent_a_id, match.agent_b_id)
            if id_ is not None
        }
        agents_map: dict = {}
        if agent_ids:
            agents_result = await self.db.execute(
                select(DebateAgent).where(DebateAgent.id.in_(agent_ids))
            )
            agents_map = {str(a.id): a for a in agents_result.scalars()}

        items = []
        for match, topic_title in rows:
            agent_a = self._agent_from_map(agents_map, match.agent_a_id)
            agent_b = self._agent_from_map(agents_map, match.agent_b_id)
            items.append({
                "id": str(match.id),
                "topic_id": str(match.topic_id),
                "topic_title": topic_title,
                "agent_a": agent_a,
                "agent_b": agent_b,
                "status": match.status,
                "winner_id": str(match.winner_id) if match.winner_id else None,
                "score_a": match.score_a,
                "score_b": match.score_b,
                "penalty_a": match.penalty_a,
                "penalty_b": match.penalty_b,
                "started_at": match.started_at,
                "finished_at": match.finished_at,
                "created_at": match.created_at,
            })

        return items, total

    def _agent_from_map(self, agents_map: dict, agent_id) -> dict:
        """배치 조회된 agents_map에서 에이전트 요약 dict를 반환.

        삭제된 에이전트(ID는 있지만 맵에 없음)와 NULL 에이전트(ID 자체가 없음)를
        각각 다른 플레이스홀더 이름으로 구분한다.

        Args:
            agents_map: str(agent_id) → DebateAgent 매핑 dict.
            agent_id: 조회할 에이전트 UUID (None 가능).

        Returns:
            id, name, provider, model_id, elo_rating, image_url 키를 포함한 dict.
        """
        if agent_id is None:
            return {"id": None, "name": "[없음]", "provider": "", "model_id": "", "elo_rating": 0, "image_url": None}
        a = agents_map.get(str(agent_id))
        if a is None:
            return {
                "id": str(agent_id), "name": "[삭제됨]",
                "provider": "", "model_id": "", "elo_rating": 0, "image_url": None,
            }
        return {
            "id": str(a.id),
            "name": a.name,
            "provider": a.provider,
            "model_id": a.model_id,
            "elo_rating": a.elo_rating,
            "image_url": a.image_url,
        }

    async def create_prediction(self, match_id: str, user_id: uuid.UUID, prediction: str) -> dict:
        """예측 투표. status='in_progress' && turn_count<=2만 허용."""
        from app.models.debate_match import DebateMatchPrediction

        result = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = result.scalar_one_or_none()
        if match is None:
            raise ValueError("Match not found")
        if match.status != "in_progress":
            raise ValueError("투표는 진행 중인 매치에서만 가능합니다")

        from app.core.config import settings as _s

        # 라운드 기준 컷오프: COUNT(*)는 A/B 발언을 각각 세므로, MAX(turn_number)로 라운드 수 판단
        completed_rounds = (await self.db.execute(
            select(func.max(DebateTurnLog.turn_number))
            .where(DebateTurnLog.match_id == match.id)
        )).scalar() or 0
        if completed_rounds > _s.debate_prediction_cutoff_turns:
            raise ValueError(f"투표 시간이 지났습니다 ({_s.debate_prediction_cutoff_turns}턴 이후 불가)")

        # 중복 검사
        dup = await self.db.execute(
            select(DebateMatchPrediction).where(
                DebateMatchPrediction.match_id == match.id,
                DebateMatchPrediction.user_id == user_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ValueError("이미 예측에 참여했습니다")

        pred = DebateMatchPrediction(match_id=match.id, user_id=user_id, prediction=prediction)
        self.db.add(pred)
        try:
            await self.db.commit()
        except IntegrityError:
            # 동시 요청으로 인한 중복 삽입 방지
            await self.db.rollback()
            raise ValueError("이미 예측에 참여했습니다")
        return {"ok": True, "prediction": prediction}

    async def get_prediction_stats(self, match_id: str, user_id: uuid.UUID) -> dict:
        """집계 + 내 투표 결과 반환."""
        from app.models.debate_match import DebateMatchPrediction

        agg = await self.db.execute(
            select(
                func.sum(sa_case((DebateMatchPrediction.prediction == "a_win", 1), else_=0)).label("a_win"),
                func.sum(sa_case((DebateMatchPrediction.prediction == "b_win", 1), else_=0)).label("b_win"),
                func.sum(sa_case((DebateMatchPrediction.prediction == "draw", 1), else_=0)).label("draw"),
                func.count().label("total"),
            ).where(DebateMatchPrediction.match_id == match_id)
        )
        row = agg.one()

        my = await self.db.execute(
            select(DebateMatchPrediction).where(
                DebateMatchPrediction.match_id == match_id,
                DebateMatchPrediction.user_id == user_id,
            )
        )
        my_pred = my.scalar_one_or_none()

        return {
            "a_win": int(row.a_win or 0),
            "b_win": int(row.b_win or 0),
            "draw": int(row.draw or 0),
            "total": int(row.total or 0),
            "my_prediction": my_pred.prediction if my_pred else None,
            "is_correct": my_pred.is_correct if my_pred else None,
        }

    async def resolve_predictions(
        self, match_id: str, winner_id: str | None, agent_a_id: str, agent_b_id: str
    ) -> None:
        """판정 후 is_correct 업데이트."""
        from app.models.debate_match import DebateMatchPrediction

        if winner_id is None:
            correct_pred = "draw"
        elif str(winner_id) == str(agent_a_id):
            correct_pred = "a_win"
        else:
            correct_pred = "b_win"

        await self.db.execute(
            sa_update(DebateMatchPrediction)
            .where(DebateMatchPrediction.match_id == match_id)
            .values(is_correct=(DebateMatchPrediction.prediction == correct_pred))
        )
        await self.db.commit()

        # 예측 결과 알림 — 핵심 경로 세션 커밋 완료 후 별도 세션으로 발송
        from app.core.database import async_session

        async with async_session() as notify_db:
            try:
                from app.services.notification_service import NotificationService
                await NotificationService(notify_db).notify_prediction_result(match_id)
                await notify_db.commit()
            except Exception:
                logger.warning("Prediction notification failed for match %s", match_id, exc_info=True)

    async def get_summary_status(self, match_id: str) -> dict:
        """요약 리포트 상태 조회. unavailable / generating / ready 반환."""
        result = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = result.scalar_one_or_none()
        if match is None:
            raise ValueError("Match not found")
        if match.status != "completed":
            return {"status": "unavailable"}
        if match.summary_report is None:
            # summary 기능이 비활성화됐거나 생성 실패 시 unavailable 반환
            from app.core.config import settings as _s
            if not _s.debate_summary_enabled:
                return {"status": "unavailable"}
            # 매치 완료 후 5분 이상 지났음에도 요약 없으면 생성 실패로 간주
            from datetime import UTC, datetime, timedelta
            if match.finished_at and (datetime.now(UTC) - match.finished_at) > timedelta(minutes=5):
                return {"status": "unavailable"}
            return {"status": "generating"}
        return {"status": "ready", **match.summary_report}

    async def toggle_featured(self, match_id: str, featured: bool) -> dict:
        """관리자 전용. 미완료 매치는 400."""
        result = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = result.scalar_one_or_none()
        if match is None:
            raise ValueError("Match not found")
        if match.status != "completed":
            raise ValueError("완료된 매치만 하이라이트로 설정 가능합니다")

        await self.db.execute(
            sa_update(DebateMatch)
            .where(DebateMatch.id == match_id)
            .values(
                is_featured=featured,
                featured_at=datetime.now(UTC) if featured else None,
            )
        )
        await self.db.commit()
        return {"ok": True, "is_featured": featured}

    async def list_featured(self, limit: int = 5) -> tuple[list[dict], int]:
        """is_featured=True, featured_at DESC. 테스트 매치 제외."""
        featured_cond = (DebateMatch.is_featured == True) & (DebateMatch.is_test.is_(False))  # noqa: E712

        total_result = await self.db.execute(
            select(func.count(DebateMatch.id)).where(featured_cond)
        )
        total = total_result.scalar() or 0

        q = (
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .where(featured_cond)
            .order_by(DebateMatch.featured_at.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(q)).all()

        agent_ids = {
            id_
            for match, _ in rows
            for id_ in (match.agent_a_id, match.agent_b_id)
            if id_ is not None
        }
        agents_map: dict = {}
        if agent_ids:
            res = await self.db.execute(select(DebateAgent).where(DebateAgent.id.in_(agent_ids)))
            agents_map = {str(a.id): a for a in res.scalars()}

        items = []
        for match, topic_title in rows:
            agent_a = self._agent_from_map(agents_map, match.agent_a_id)
            agent_b = self._agent_from_map(agents_map, match.agent_b_id)
            items.append({
                "id": str(match.id),
                "topic_id": str(match.topic_id),
                "topic_title": topic_title,
                "agent_a": agent_a,
                "agent_b": agent_b,
                "status": match.status,
                "winner_id": str(match.winner_id) if match.winner_id else None,
                "score_a": match.score_a,
                "score_b": match.score_b,
                "is_featured": match.is_featured,
                "featured_at": match.featured_at,
                "started_at": match.started_at,
                "finished_at": match.finished_at,
                "created_at": match.created_at,
            })
        return items, total


# --- DebateSummaryService ---

SUMMARY_SYSTEM_PROMPT = """당신은 AI 토론 분석 전문가입니다. 토론 로그와 판정 결과를 분석하여 JSON 형식으로 요약을 생성하세요.

반드시 다음 JSON 형식으로만 응답하세요:
{
  "agent_a_arguments": ["에이전트A의 핵심 논거 1", "핵심 논거 2"],
  "agent_b_arguments": ["에이전트B의 핵심 논거 1", "핵심 논거 2"],
  "turning_points": ["승부를 가른 결정적 순간 또는 논거 대립 1", "순간 2"],
  "overall_summary": "판정 결과를 포함한 전체 토론 총평 (3-4문장)"
}

작성 기준:
- agent_a_arguments / agent_b_arguments: 각 에이전트가 실제로 제시한 고유한 논거만 포함. 반복 주장은 하나로 합친다.
- turning_points: 실질적인 승패 갈림 지점이 없으면 빈 배열을 반환한다.
- overall_summary: 어떤 논거가 왜 더 설득력이 있었는지, 판정 결과를 자연스럽게 포함한다."""


def _format_summary_log(turns: list, agent_a_name: str, agent_b_name: str) -> str:
    """턴 로그를 텍스트로 포맷하여 요약 LLM에 전달한다.

    발언 내용(action, claim, evidence)만 포함하고 점수·메타데이터는 제외한다.

    Args:
        turns: DebateTurnLog 목록.
        agent_a_name: 에이전트 A 이름.
        agent_b_name: 에이전트 B 이름.

    Returns:
        LLM 입력용 포맷된 문자열.
    """
    name_map = {"agent_a": agent_a_name, "agent_b": agent_b_name}
    lines = []
    for t in turns:
        speaker_name = name_map.get(t.speaker, t.speaker)
        lines.append(f"[{speaker_name} 턴 {t.turn_number}] {t.action}: {t.claim}")
        if t.evidence:
            lines.append(f"  근거: {t.evidence}")
    return "\n".join(lines)


def _build_rule_violations(turns: list, agent_a_name: str, agent_b_name: str) -> list[str]:
    """review_result의 violations 데이터를 사람이 읽을 수 있는 문자열 목록으로 변환.

    Args:
        turns: DebateTurnLog 목록.
        agent_a_name: 에이전트 A 이름.
        agent_b_name: 에이전트 B 이름.

    Returns:
        '[에이전트명] 턴N: 위반유형(severity) — 설명' 형식의 문자열 목록.
    """
    name_map = {"agent_a": agent_a_name, "agent_b": agent_b_name}
    violations = []
    for t in turns:
        rr = t.review_result or {}
        for v in rr.get("violations", []):
            v_type = v.get("type", "")
            severity = v.get("severity", "")
            detail = v.get("detail", "")
            speaker_name = name_map.get(t.speaker, t.speaker)
            violations.append(f"[{speaker_name}] 턴{t.turn_number}: {v_type}({severity}) — {detail}")
    return violations


class DebateSummaryService:
    """매치 완료 후 LLM 기반 요약 리포트를 생성하는 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_summary(self, match_id: str) -> None:
        """매치 완료 후 비동기 호출. 이미 summary_report가 있으면 스킵.

        LLM을 호출해 에이전트 논거, 전환점, 전체 총평을 JSON으로 생성하고
        DebateMatch.summary_report에 저장한다.

        Args:
            match_id: 요약을 생성할 매치 UUID 문자열.
        """
        res = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = res.scalar_one_or_none()
        if match is None or match.status != "completed":
            return
        if match.summary_report is not None:
            return  # 중복 방지

        # 에이전트 조회 — 이름·owner_id 모두 필요해 객체로 유지
        agents_res = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id.in_([match.agent_a_id, match.agent_b_id]))
        )
        agents_map = {str(a.id): a for a in agents_res.scalars().all()}
        agent_a_name = agents_map[str(match.agent_a_id)].name if str(match.agent_a_id) in agents_map else "Agent A"
        agent_b_name = agents_map[str(match.agent_b_id)].name if str(match.agent_b_id) in agents_map else "Agent B"

        # 턴 로그 조회
        turns_res = await self.db.execute(
            select(DebateTurnLog)
            .where(DebateTurnLog.match_id == match.id)
            .order_by(DebateTurnLog.turn_number)
        )
        turns = list(turns_res.scalars().all())
        if not turns:
            return

        log_text = _format_summary_log(turns, agent_a_name, agent_b_name)
        rule_violations = _build_rule_violations(turns, agent_a_name, agent_b_name)

        # 판정 결과 요약 — 승자 이름을 resolving하여 컨텍스트에 포함
        if match.winner_id is None:
            result_summary = "판정: 무승부"
        elif str(match.winner_id) == str(match.agent_a_id):
            result_summary = f"판정: {agent_a_name} 승리 (점수: {match.score_a} vs {match.score_b})"
        else:
            result_summary = f"판정: {agent_b_name} 승리 (점수: {match.score_b} vs {match.score_a})"

        try:
            from app.services.llm.inference_client import InferenceClient

            # llm_models 테이블에서 요약 모델 조회 — Langfuse 추적 및 토큰 로그 기록에 필요
            model_res = await self.db.execute(
                select(LLMModel).where(LLMModel.model_id == settings.debate_summary_model)
            )
            llm_model = model_res.scalar_one_or_none()
            if llm_model is None:
                logger.warning(
                    "Summary skipped for match %s: model '%s' not found in llm_models",
                    match_id,
                    settings.debate_summary_model,
                )
                return

            messages = [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"참가자: {agent_a_name}(찬성) vs {agent_b_name}(반대)\n"
                        f"{result_summary}\n\n"
                        f"토론 로그:\n\n{log_text[:4000]}"
                    ),
                },
            ]

            async with InferenceClient() as client:
                result = await client.generate(
                    model=llm_model,
                    messages=messages,
                    max_tokens=800,
                    temperature=0.3,
                )

            parsed = _extract_json_from_response(result["content"])
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)

            # 토큰 사용량 기록 — agent_a 소유자를 사용량 귀속 대상으로 지정 (위에서 조회한 agents_map 재사용)
            agent_a_obj = agents_map.get(str(match.agent_a_id))
            if agent_a_obj is not None and (input_tokens > 0 or output_tokens > 0):
                input_cost = calculate_token_cost(input_tokens, llm_model.input_cost_per_1m)
                output_cost = calculate_token_cost(output_tokens, llm_model.output_cost_per_1m)
                self.db.add(TokenUsageLog(
                    user_id=agent_a_obj.owner_id,
                    session_id=None,
                    llm_model_id=llm_model.id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=input_cost + output_cost,
                ))

            summary_report = {
                "agent_a_arguments": parsed.get("agent_a_arguments", []),
                "agent_b_arguments": parsed.get("agent_b_arguments", []),
                "turning_points": parsed.get("turning_points", []),
                "rule_violations": rule_violations,  # LLM 재해석 없이 review_result 데이터 직접 활용
                "overall_summary": parsed.get("overall_summary", ""),
                "generated_at": datetime.now(UTC).isoformat(),
                "model_used": settings.debate_summary_model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            await self.db.execute(
                sa_update(DebateMatch)
                .where(DebateMatch.id == match.id)
                .values(summary_report=summary_report)
            )
            await self.db.commit()
            logger.info("Summary generated for match %s", match_id)

        except json.JSONDecodeError as exc:
            logger.warning("Summary JSON parse failed for match %s: %s", match_id, exc)
        except Exception as exc:
            logger.warning("Summary generation failed for match %s: %s", match_id, exc)


async def generate_summary_task(match_id: str) -> None:
    """백그라운드 태스크용 요약 생성 진입점 — 앱 수준 세션 재사용.

    MatchFinalizer에서 asyncio.create_task()로 호출된다.
    DB 세션을 독립적으로 생성해 엔진 세션과 격리한다.

    Args:
        match_id: 요약을 생성할 매치 UUID 문자열.
    """
    from app.core.database import async_session

    async with async_session() as db:
        service = DebateSummaryService(db)
        await service.generate_summary(match_id)
