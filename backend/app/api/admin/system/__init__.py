from fastapi import APIRouter

from app.api.admin.system import llm_models, monitoring, usage, users

router = APIRouter()
router.include_router(llm_models.router, prefix="/llm-models", tags=["admin-system-llm"])
router.include_router(monitoring.router, prefix="/monitoring", tags=["admin-system-monitoring"])
router.include_router(usage.router, prefix="/usage", tags=["admin-system-usage"])
router.include_router(users.router, prefix="/users", tags=["admin-system-users"])

__all__ = ["llm_models", "monitoring", "router", "usage", "users"]
