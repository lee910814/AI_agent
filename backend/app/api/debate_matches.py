"""토론 매치 API 라우터 — 매치 조회, SSE 스트림, 예측투표, 요약."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.debate_match import DebateMatch
from app.models.user import User
from app.schemas.debate_match import PredictionCreate, TurnLogResponse
from app.services.debate.broadcast import subscribe
from app.services.debate.match_service import DebateMatchService

router = APIRouter()


@router.get("/featured")
async def get_featured_matches(
    limit: int = Query(5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """하이라이트 매치 목록."""
    service = DebateMatchService(db)
    items, total = await service.list_featured(limit=limit)
    return {"items": items, "total": total}


@router.get("/{match_id}/viewers")
async def get_viewer_count(
    match_id: str,
    user: User = Depends(get_current_user),
):
    """현재 관전자 수 조회. Redis Set debate:viewers:{match_id}"""
    from app.core.redis import redis_client

    count = await redis_client.scard(f"debate:viewers:{match_id}")
    return {"count": count}


@router.post("/{match_id}/predictions", status_code=status.HTTP_201_CREATED)
async def create_prediction(
    match_id: str,
    data: PredictionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """예측 투표. in_progress 매치 && turn_count<=2만 허용."""
    service = DebateMatchService(db)
    try:
        return await service.create_prediction(match_id, user.id, data.prediction)
    except ValueError as exc:
        detail = str(exc)
        if "DUPLICATE" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 투표했습니다") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc


@router.get("/{match_id}/predictions")
async def get_predictions(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """예측 투표 통계 및 내 투표 결과 조회."""
    service = DebateMatchService(db)
    return await service.get_prediction_stats(match_id, user.id)


@router.get("/{match_id}/summary")
async def get_match_summary(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토론 요약 리포트 조회. 생성 중이면 generating, 완료면 ready."""
    service = DebateMatchService(db)
    try:
        return await service.get_summary_status(match_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found") from exc


@router.get("/{match_id}")
async def get_match(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """매치 상세 조회."""
    service = DebateMatchService(db)
    match = await service.get_match(match_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return match


@router.get("/{match_id}/turns", response_model=list[TurnLogResponse])
async def get_match_turns(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """매치 턴 로그 조회."""
    service = DebateMatchService(db)
    turns = await service.get_match_turns(match_id)
    return [TurnLogResponse.model_validate(t) for t in turns]


@router.get("/{match_id}/scorecard")
async def get_scorecard(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """스코어카드 조회."""
    service = DebateMatchService(db)
    scorecard = await service.get_scorecard(match_id)
    if scorecard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scorecard not available")
    return scorecard


@router.get("/{match_id}/stream")
async def stream_match(
    match_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """매치 라이브 SSE 스트림.

    이미 종료된 매치: 즉시 finished/error 이벤트 반환 — Redis pub/sub 이벤트 손실 방지.
    진행 중 매치: Redis pub/sub 구독으로 실시간 스트림.
    """
    sse_headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}

    res = await db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
    match = res.scalar_one_or_none()

    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    if match.status in ("completed", "error", "forfeit"):
        # SSE 연결 전에 이미 종료된 매치 — 즉시 종료 이벤트를 합성해 반환
        async def _immediate():
            if match.status == "completed":
                payload = json.dumps(
                    {"event": "finished", "data": {
                        "winner_id": str(match.winner_id) if match.winner_id else None,
                        "score_a": match.score_a,
                        "score_b": match.score_b,
                    }},
                    default=str,
                )
            elif match.status == "forfeit":
                payload = json.dumps(
                    {"event": "forfeit", "data": {"winner_id": str(match.winner_id) if match.winner_id else None}},
                    default=str,
                )
            else:
                payload = json.dumps({"event": "error", "data": {"message": "Match ended with error"}}, default=str)
            yield f"data: {payload}\n\n"

        return StreamingResponse(_immediate(), media_type="text/event-stream", headers=sse_headers)

    return StreamingResponse(
        subscribe(match_id, user_id=str(user.id)),
        media_type="text/event-stream",
        headers=sse_headers,
    )


@router.get("")
async def list_matches(
    topic_id: str | None = None,
    agent_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """매치 목록 조회. topic_id 또는 agent_id 기준으로 필터링 가능.

    Args:
        topic_id: 특정 토픽의 매치만 조회 (선택).
        agent_id: 특정 에이전트가 참가한 매치만 조회 (선택).
        status_filter: 매치 상태 필터 (선택).
        skip: 페이지네이션 오프셋.
        limit: 반환할 최대 항목 수.
        user: 인증된 현재 사용자.
        db: 비동기 DB 세션.

    Returns:
        items와 total 필드를 포함한 딕셔너리.
    """
    service = DebateMatchService(db)
    items, total = await service.list_matches(
        topic_id=topic_id, agent_id=agent_id, status=status_filter, skip=skip, limit=limit
    )
    return {"items": items, "total": total}
