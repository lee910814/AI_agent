from fastapi import APIRouter

from app.api.admin.debate import agents, matches, seasons, templates, topics, tournaments

router = APIRouter()
router.include_router(agents.router, tags=["admin-debate-agents"])
router.include_router(matches.router, tags=["admin-debate-matches"])
router.include_router(seasons.router, tags=["admin-debate-seasons"])
router.include_router(topics.router, tags=["admin-debate-stats"])
router.include_router(templates.router, tags=["admin-debate-templates"])
router.include_router(tournaments.router, tags=["admin-debate-tournaments"])

__all__ = ["agents", "matches", "router", "seasons", "templates", "topics", "tournaments"]
