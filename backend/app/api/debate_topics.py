"""토론 토픽 API 라우터 — 토픽 CRUD, 큐 등록/탈퇴, SSE 대기방."""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func as sqlfunc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import QueueConflictError
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch, DebateMatchQueue
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.schemas.debate_match import JoinQueueRequest
from app.schemas.debate_topic import TopicCreate, TopicListResponse, TopicResponse, TopicUpdatePayload
from app.services.debate.broadcast import publish_queue_event, subscribe_queue
from app.services.debate.engine import run_debate
from app.services.debate.matching_service import DebateMatchingService
from app.services.debate.topic_service import DebateTopicService

logger = logging.getLogger(__name__)

router = APIRouter()


async def _require_agent_ownership(db: AsyncSession, agent_id: str, user: User) -> None:
    """에이전트 소유권 검증. 실패 시 HTTP 403.

    Args:
        db: 비동기 DB 세션.
        agent_id: 검증할 에이전트 ID.
        user: 소유권을 확인할 사용자.

    Raises:
        HTTPException(403): 사용자가 에이전트 소유자가 아닐 때.
    """
    agent_result = await db.execute(
        select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent not owned by user")


@router.post("", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    data: TopicCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토론 주제 생성. 모든 사용자가 스케줄 설정 가능, 관리자 여부는 is_admin_topic 플래그로만 구분."""
    service = DebateTopicService(db)
    try:
        topic = await service.create_topic(data, user)
    except ValueError as exc:
        detail = str(exc)
        if "한도" in detail:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return _topic_response(topic)


@router.get("", response_model=TopicListResponse)
async def list_topics(
    status_filter: str | None = Query(None, alias="status", pattern="^(scheduled|open|in_progress|closed)$"),
    sort: str = Query("recent", pattern="^(recent|popular_week|queue|matches)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토픽 목록 조회. 상태 필터와 정렬 기준 지정 가능.

    Args:
        status_filter: 상태 필터 (scheduled|open|in_progress|closed, 선택).
        sort: 정렬 기준 (recent|popular_week|queue|matches).
        page: 페이지 번호.
        page_size: 페이지당 항목 수.
        user: 인증된 현재 사용자.
        db: 비동기 DB 세션.

    Returns:
        items와 total 필드를 포함한 TopicListResponse.
    """
    service = DebateTopicService(db)
    items, total = await service.list_topics(status=status_filter, sort=sort, page=page, page_size=page_size)
    return {"items": items, "total": total}


@router.patch("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: UUID,
    payload: TopicUpdatePayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """주제 작성자가 자신의 주제를 수정."""
    service = DebateTopicService(db)
    try:
        topic = await service.update_topic_by_user(topic_id, user.id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _topic_response(topic)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """주제 작성자가 자신의 주제를 삭제. 진행 중 매치가 있으면 409 반환."""
    service = DebateTopicService(db)
    try:
        await service.delete_topic_by_user(topic_id, user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토픽 상세 조회. 큐 대기 수와 매치 수 포함.

    Args:
        topic_id: 조회할 토픽 ID.
        user: 인증된 현재 사용자.
        db: 비동기 DB 세션.

    Returns:
        TopicResponse — 큐/매치 카운트가 포함된 토픽 상세 정보.

    Raises:
        HTTPException(404): 토픽이 존재하지 않을 때.
    """
    service = DebateTopicService(db)
    topic = await service.get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    queue_count = await service.count_queue(topic.id)
    match_count = await service.count_matches(topic.id)
    return _topic_response(topic, queue_count=queue_count, match_count=match_count)


async def _run_debate_safe(match_id: str) -> None:
    """토론 엔진 실행 래퍼. 예외를 로깅하고 삼키지 않음.

    Args:
        match_id: 실행할 매치 ID.
    """
    try:
        await run_debate(match_id)
    except Exception:
        logger.exception("토론 엔진 오류 (match_id=%s)", match_id)


_background_tasks: set[asyncio.Task] = set()


async def _auto_match_safe(topic_id: str, agent_a_id: str, agent_b_id: str) -> None:
    """한 명 준비 완료 후 카운트다운, 양쪽이 아직 큐에 있으면 자동 매치 생성.

    카운트다운(debate_ready_countdown_seconds) 후 두 에이전트가 모두 큐에 남아
    있으면 DebateMatch를 생성하고 토론 엔진을 백그라운드로 실행한다.

    Args:
        topic_id: 매치가 생성될 토픽 ID.
        agent_a_id: 준비 완료한 에이전트 ID.
        agent_b_id: 상대 에이전트 ID.
    """
    await asyncio.sleep(settings.debate_ready_countdown_seconds)

    from app.core.database import async_session

    try:
        async with async_session() as db:
            # 두 엔트리를 단일 쿼리로 함께 잠금 — 분리 잠금 시 ready_up과 경합 방지
            entries = (await db.execute(
                select(DebateMatchQueue)
                .where(
                    DebateMatchQueue.topic_id == topic_id,
                    DebateMatchQueue.agent_id.in_([agent_a_id, agent_b_id]),
                )
                .with_for_update()
            )).scalars().all()

            if len(entries) < 2:
                # 이미 ready_up에서 처리됨
                return

            entry_a = next(e for e in entries if str(e.agent_id) == agent_a_id)
            entry_b = next(e for e in entries if str(e.agent_id) == agent_b_id)

            from app.services.debate.agent_service import get_latest_version
            from app.services.debate.promotion_service import DebatePromotionService
            from app.services.debate.season_service import DebateSeasonService

            ver_a = await get_latest_version(db, entry_a.agent_id)
            ver_b = await get_latest_version(db, entry_b.agent_id)

            match = DebateMatch(
                topic_id=topic_id,
                agent_a_id=entry_a.agent_id,
                agent_b_id=entry_b.agent_id,
                agent_a_version_id=ver_a.id if ver_a else None,
                agent_b_version_id=ver_b.id if ver_b else None,
                status="pending",
            )

            # ready_up()과 동일하게 활성 시즌·시리즈 태깅
            season_svc = DebateSeasonService(db)
            active_season = await season_svc.get_active_season()
            if active_season:
                match.season_id = active_season.id

            promo_svc = DebatePromotionService(db)
            for aid in [str(entry_a.agent_id), str(entry_b.agent_id)]:
                series = await promo_svc.get_active_series(aid)
                if series and match.series_id is None:
                    match.match_type = series.series_type
                    match.series_id = series.id

            db.add(match)
            await db.delete(entry_a)
            await db.delete(entry_b)
            await db.commit()
            await db.refresh(match)

            logger.info("카운트다운 자동 매치 생성: %s (topic=%s)", match.id, topic_id)

            await publish_queue_event(topic_id, agent_a_id, "matched", {
                "match_id": str(match.id),
                "opponent_agent_id": agent_b_id,
                "auto_matched": False,
            })
            await publish_queue_event(topic_id, agent_b_id, "matched", {
                "match_id": str(match.id),
                "opponent_agent_id": agent_a_id,
                "auto_matched": False,
            })

            # create_task로 토론 실행 — BackgroundTask 컨텍스트 즉시 반환
            task = asyncio.create_task(_run_debate_safe(str(match.id)))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
    except Exception:
        logger.exception("카운트다운 자동 매치 오류 (topic=%s)", topic_id)


@router.post("/random-match")
async def random_match(
    data: JoinQueueRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """랜덤 매칭. 비밀번호 없는 open 토픽 중 대기자 있는 토픽을 우선 선택."""
    await _require_agent_ownership(db, str(data.agent_id), user)

    # 다른 사용자의 대기자가 있는 비밀번호 없는 open 토픽 우선
    queue_subq = (
        select(DebateMatchQueue.topic_id)
        .where(DebateMatchQueue.user_id != user.id)
        .group_by(DebateMatchQueue.topic_id)
        .subquery()
    )
    topic_result = await db.execute(
        select(DebateTopic)
        .join(queue_subq, DebateTopic.id == queue_subq.c.topic_id)
        .where(DebateTopic.status == "open", DebateTopic.is_password_protected == False)  # noqa: E712
        .order_by(sqlfunc.random())
        .limit(1)
    )
    topic = topic_result.scalar_one_or_none()

    if topic is None:
        # 대기자 없으면 아무 open 비밀번호없는 토픽에 합류
        topic_result = await db.execute(
            select(DebateTopic)
            .where(DebateTopic.status == "open", DebateTopic.is_password_protected == False)  # noqa: E712
            .order_by(sqlfunc.random())
            .limit(1)
        )
        topic = topic_result.scalar_one_or_none()

    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="현재 참여 가능한 토픽이 없습니다",
        )

    service = DebateMatchingService(db)
    try:
        result = await service.join_queue(user, str(topic.id), str(data.agent_id))
    except QueueConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "existing_topic_id": exc.existing_topic_id},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"topic_id": str(topic.id), **result}


@router.post("/{topic_id}/join")
async def join_topic_queue(
    topic_id: str,
    data: JoinQueueRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """토픽 큐 참가. 상대가 있으면 opponent_joined 이벤트 발행."""
    service = DebateMatchingService(db)
    try:
        result = await service.join_queue(user, topic_id, str(data.agent_id), data.password)
    except QueueConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "existing_topic_id": exc.existing_topic_id},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result


@router.post("/{topic_id}/queue/ready")
async def ready_up_queue(
    topic_id: str,
    data: JoinQueueRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """준비 완료 버튼. 양쪽 모두 준비되면 매치 생성 후 토론 시작."""
    service = DebateMatchingService(db)
    try:
        result = await service.ready_up(user, topic_id, data.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if result.get("status") == "matched" and result.get("match_id"):
        background_tasks.add_task(_run_debate_safe, result["match_id"])
    elif result.get("countdown_started") and result.get("opponent_agent_id"):
        # 한 명이 먼저 준비 완료 → 10초 후 자동 매치
        background_tasks.add_task(
            _auto_match_safe, topic_id, str(data.agent_id), result["opponent_agent_id"]
        )

    return result


@router.get("/{topic_id}/queue/stream")
async def queue_stream(
    topic_id: str,
    agent_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """대기방 SSE 스트림. 매치/타임아웃/취소 이벤트를 수신."""
    await _require_agent_ownership(db, agent_id, user)

    # 큐 등록 여부 확인
    queue_result = await db.execute(
        select(DebateMatchQueue).where(
            DebateMatchQueue.topic_id == topic_id,
            DebateMatchQueue.agent_id == agent_id,
        )
    )
    in_queue = queue_result.scalar_one_or_none() is not None

    if not in_queue:
        # SSE 연결 전 이미 매칭된 경우 → 즉시 matched 이벤트 반환
        # (2번째 플레이어가 큐에서 제거된 직후 대기방에 도달하는 레이스 컨디션 처리)
        match_result = await db.execute(
            select(DebateMatch)
            .where(
                DebateMatch.topic_id == topic_id,
                (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id),
            )
            .order_by(DebateMatch.created_at.desc())
            .limit(1)
        )
        match = match_result.scalar_one_or_none()
        if match is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent not in queue")

        opponent_id = str(match.agent_b_id) if str(match.agent_a_id) == agent_id else str(match.agent_a_id)
        payload = json.dumps(
            {
                "event": "matched",
                "data": {"match_id": str(match.id), "opponent_agent_id": opponent_id, "auto_matched": False},
            },
            ensure_ascii=False,
        )

        async def _immediate_matched():
            yield f"data: {payload}\n\n"

        return StreamingResponse(
            _immediate_matched(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return StreamingResponse(
        subscribe_queue(topic_id, agent_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{topic_id}/queue/status")
async def queue_status(
    topic_id: str,
    agent_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 큐 상태 조회."""
    await _require_agent_ownership(db, agent_id, user)

    # 큐 엔트리 확인
    queue_result = await db.execute(
        select(DebateMatchQueue).where(
            DebateMatchQueue.topic_id == topic_id,
            DebateMatchQueue.agent_id == agent_id,
        )
    )
    entry = queue_result.scalar_one_or_none()
    if entry is not None:
        # 상대방 큐 엔트리 확인
        opp_result = await db.execute(
            select(DebateMatchQueue).where(
                DebateMatchQueue.topic_id == topic_id,
                DebateMatchQueue.agent_id != agent_id,
            ).order_by(DebateMatchQueue.joined_at).limit(1)
        )
        opp_entry = opp_result.scalar_one_or_none()
        return {
            "status": "queued",
            "position": 1,
            "joined_at": entry.joined_at.isoformat(),
            "is_ready": entry.is_ready,
            "opponent_agent_id": str(opp_entry.agent_id) if opp_entry else None,
            "opponent_is_ready": opp_entry.is_ready if opp_entry else False,
        }

    # 이미 매칭됐는지 확인 (최근 매치)
    match_result = await db.execute(
        select(DebateMatch).where(
            DebateMatch.topic_id == topic_id,
            (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id),
        ).order_by(DebateMatch.created_at.desc()).limit(1)
    )
    match = match_result.scalar_one_or_none()
    if match is not None:
        opponent_id = str(match.agent_b_id) if str(match.agent_a_id) == agent_id else str(match.agent_a_id)
        return {"status": "matched", "match_id": str(match.id), "opponent_agent_id": opponent_id}

    return {"status": "not_in_queue"}


@router.delete("/{topic_id}/queue")
async def leave_queue(
    topic_id: str,
    agent_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """큐 탈퇴. 대기 취소 이벤트 발행."""
    await _require_agent_ownership(db, agent_id, user)

    queue_result = await db.execute(
        select(DebateMatchQueue).where(
            DebateMatchQueue.topic_id == topic_id,
            DebateMatchQueue.agent_id == agent_id,
        )
    )
    entry = queue_result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in queue")

    await db.delete(entry)
    await db.commit()

    await publish_queue_event(topic_id, agent_id, "cancelled", {})
    return {"status": "left"}


def _topic_response(topic, queue_count: int = 0, match_count: int = 0) -> dict:
    """DebateTopic 모델을 API 응답 딕셔너리로 직렬화.

    Args:
        topic: DebateTopic ORM 모델 인스턴스.
        queue_count: 현재 큐 대기자 수 (기본값 0).
        match_count: 해당 토픽의 총 매치 수 (기본값 0).

    Returns:
        API 응답에 사용할 토픽 딕셔너리.
    """
    return {
        "id": topic.id,
        "title": topic.title,
        "description": topic.description,
        "mode": topic.mode,
        "status": topic.status,
        "max_turns": topic.max_turns,
        "turn_token_limit": topic.turn_token_limit,
        "scheduled_start_at": topic.scheduled_start_at,
        "scheduled_end_at": topic.scheduled_end_at,
        "is_admin_topic": topic.is_admin_topic,
        "is_password_protected": getattr(topic, "is_password_protected", False),
        "tools_enabled": topic.tools_enabled,
        "queue_count": queue_count,
        "match_count": match_count,
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
        "created_by": str(topic.created_by) if topic.created_by else None,
        "creator_nickname": topic.creator_nickname if hasattr(topic, "creator_nickname") else None,
    }
