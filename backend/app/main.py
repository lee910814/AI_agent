import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api import (
    auth,
    community,
    follows,
    health,
    models,
    notifications,
    uploads,
    usage,
)
from app.api.admin.debate import agents as admin_debate_agents
from app.api.admin.debate import matches as admin_debate_matches
from app.api.admin.debate import seasons as admin_debate_seasons
from app.api.admin.debate import templates as admin_debate_templates
from app.api.admin.debate import topics as admin_debate_topics
from app.api.admin.debate import tournaments as admin_debate_tournaments
from app.api.admin.system import llm_models as admin_llm_models
from app.api.admin.system import monitoring as admin_monitoring
from app.api.admin.system import usage as admin_usage
from app.api.admin.system import users as admin_users
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import AppError
from app.core.observability import flush_langfuse, init_sentry, setup_prometheus
from app.core.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

# Sentry 초기화 (앱 모듈 로드 시 즉시)
init_sentry()


async def _runpod_warmer() -> None:
    """RunPod Serverless 콜드스타트 방지 — 5분마다 최소 토큰 요청으로 워커 warm 유지."""
    import httpx

    if not settings.runpod_api_key or not settings.runpod_endpoint_id:
        return

    base_url = f"https://api.runpod.ai/v2/{settings.runpod_endpoint_id}/runsync"
    headers = {"Authorization": f"Bearer {settings.runpod_api_key}", "Content-Type": "application/json"}
    # 워머는 연결 유지가 목적이므로 최소 페이로드 사용
    body = {"input": {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}}

    while True:
        await asyncio.sleep(300)  # 5분 대기
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(base_url, headers=headers, json=body)
                logger.debug("RunPod warmer ping: status=%s", resp.status_code)
        except Exception as exc:
            logger.debug("RunPod warmer ping failed (non-critical): %s", exc)


async def _retry_missing_summaries() -> None:
    """앱 시작 시 summary_report가 없는 completed 매치에 대해 요약 생성을 재시도한다.

    컨테이너 재시작으로 백그라운드 태스크가 취소된 경우 복구용.
    10분 이상 지난 매치만 대상 (현재 진행 중인 태스크와 겹치지 않도록).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.core.database import async_session
    from app.models.debate_match import DebateMatch
    from app.services.debate.match_service import generate_summary_task

    await asyncio.sleep(10)  # 서버 완전 시작 대기

    async with async_session() as db:
        cutoff = datetime.now(UTC) - timedelta(minutes=10)
        res = await db.execute(
            select(DebateMatch.id).where(
                DebateMatch.status == "completed",
                DebateMatch.summary_report.is_(None),
                DebateMatch.finished_at < cutoff,
            ).limit(30)
        )
        match_ids = [str(r) for r in res.scalars().all()]

    if match_ids:
        logger.info("Retrying summary generation for %d matches", len(match_ids))
        for match_id in match_ids:
            asyncio.create_task(generate_summary_task(match_id))
            await asyncio.sleep(3)  # API rate limit 방지


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 토론 자동 매칭 태스크 + WS pub/sub 리스너 시작
    if settings.debate_enabled:
        from app.services.debate.auto_matcher import DebateAutoMatcher
        from app.services.debate.ws_manager import WSConnectionManager

        auto_matcher = DebateAutoMatcher.get_instance()
        auto_matcher.start()

        ws_manager = WSConnectionManager.get_instance()
        await ws_manager.start_pubsub_listener()

    # 컨테이너 재시작으로 취소된 요약 태스크 복구
    if settings.debate_summary_enabled:
        asyncio.create_task(_retry_missing_summaries())

    # RunPod 콜드스타트 방지 워머 (runpod_api_key·endpoint_id 미설정 시 내부에서 즉시 반환)
    asyncio.create_task(_runpod_warmer())

    yield

    # 토론 자동 매칭 태스크 + WS pub/sub 리스너 중지
    if settings.debate_enabled:
        auto_matcher.stop()
        await ws_manager.stop_pubsub_listener()
    # Langfuse 버퍼 플러시 후 종료
    flush_langfuse()
    await engine.dispose()


app = FastAPI(
    title="AI 에이전트 토론 플랫폼 API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# Prometheus 계측 (/metrics 엔드포인트 노출)
setup_prometheus(app)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(NotImplementedError)
async def not_implemented_handler(request: Request, exc: NotImplementedError):
    return JSONResponse(status_code=501, content={"detail": "Not implemented"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """프로덕션에서 내부 에러 메시지 노출 방지."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    if settings.debug:
        return JSONResponse(status_code=500, content={"detail": str(exc)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Cookie"],
)

app.add_middleware(RateLimitMiddleware)

# User-facing routes
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(follows.router, prefix="/api/follows", tags=["follows"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(community.router, prefix="/api/community", tags=["community"])

# Debate routes (feature flag)
if settings.debate_enabled:
    from app.api import debate_agents, debate_matches, debate_topics, debate_tournaments, debate_ws

    app.include_router(debate_agents.router, prefix="/api/agents", tags=["debate-agents"])
    app.include_router(debate_topics.router, prefix="/api/topics", tags=["debate-topics"])
    app.include_router(debate_matches.router, prefix="/api/matches", tags=["debate-matches"])
    app.include_router(debate_tournaments.router, prefix="/api/tournaments", tags=["tournaments"])
    app.include_router(debate_ws.router, tags=["debate-ws"])

# Admin routes
app.include_router(admin_users.router, prefix="/api/admin/users", tags=["admin-users"])
app.include_router(admin_llm_models.router, prefix="/api/admin/models", tags=["admin-models"])
app.include_router(admin_usage.router, prefix="/api/admin/usage", tags=["admin-usage"])
app.include_router(admin_monitoring.router, prefix="/api/admin/monitoring", tags=["admin-monitoring"])
if settings.debate_enabled:
    _debate_prefix = "/api/admin/debate"
    _debate_tags = ["admin-debate"]
    app.include_router(admin_debate_topics.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_matches.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_agents.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_seasons.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_tournaments.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_templates.router, prefix=_debate_prefix, tags=_debate_tags)

# 업로드 파일 디렉토리 생성
os.makedirs(settings.upload_dir, exist_ok=True)


@app.get("/uploads/{path:path}")
async def serve_upload_file(path: str):
    """업로드 파일 서빙 (인증 불필요 — 프로필 이미지는 공개 자원)."""
    upload_dir = Path(settings.upload_dir).resolve()
    file_path = (upload_dir / path).resolve()

    # 경로 순회 공격 방지
    if not file_path.is_relative_to(upload_dir):
        return JSONResponse(status_code=403, content={"detail": "Access denied"})
    if not file_path.is_file():
        return JSONResponse(status_code=404, content={"detail": "File not found"})

    return FileResponse(str(file_path))
