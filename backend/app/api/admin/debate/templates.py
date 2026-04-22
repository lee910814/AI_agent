"""관리자 에이전트 템플릿 관리."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.user import User
from app.schemas.debate_agent import AgentTemplateAdminResponse, AgentTemplateCreate, AgentTemplateUpdate
from app.services.debate.template_service import DebateTemplateService

router = APIRouter()


@router.get("/templates", response_model=list[AgentTemplateAdminResponse])
async def list_templates_admin(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 템플릿 목록 (비활성 포함)."""
    service = DebateTemplateService(db)
    templates = await service.list_all_templates()
    return [AgentTemplateAdminResponse.model_validate(t) for t in templates]


@router.get("/templates/{template_id}", response_model=AgentTemplateAdminResponse)
async def get_template_admin(
    template_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """템플릿 상세 조회."""
    service = DebateTemplateService(db)
    template = await service.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return AgentTemplateAdminResponse.model_validate(template)


@router.post(
    "/templates",
    response_model=AgentTemplateAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: AgentTemplateCreate,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """템플릿 생성 (superadmin 전용)."""
    service = DebateTemplateService(db)
    try:
        template = await service.create_template(data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return AgentTemplateAdminResponse.model_validate(template)


@router.patch("/templates/{template_id}", response_model=AgentTemplateAdminResponse)
async def update_template(
    template_id: str,
    data: AgentTemplateUpdate,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """템플릿 수정 (superadmin 전용)."""
    service = DebateTemplateService(db)
    try:
        template = await service.update_template(template_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AgentTemplateAdminResponse.model_validate(template)
