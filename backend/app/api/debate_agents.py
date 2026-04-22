"""토론 에이전트 API 라우터 — CRUD, 랭킹, 갤러리, H2H, 승급전."""

import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.debate_agent import DebateAgent
from app.models.user import User
from app.schemas.debate_agent import (
    AgentCreate,
    AgentPublicResponse,
    AgentRankingListResponse,
    AgentResponse,
    AgentTemplateResponse,
    AgentUpdate,
    AgentVersionResponse,
    CloneRequest,
    GalleryListResponse,
    HeadToHeadListResponse,
    PromotionSeriesResponse,
)
from app.services.debate.agent_service import DebateAgentService
from app.services.debate.template_service import DebateTemplateService
from app.services.debate.ws_manager import WSConnectionManager

router = APIRouter()

# 관리자 역할 집합 — 소유권 우회 가능 (변경 시 이 한 곳만 수정)
_ADMIN_ROLES: frozenset[str] = frozenset({"admin", "superadmin"})


async def _require_agent_access(service: DebateAgentService, agent_id: str, user: User) -> DebateAgent:
    """에이전트 존재 확인 + 접근 권한 검증. 소유자 또는 관리자만 허용.

    Args:
        service: 에이전트 서비스 인스턴스.
        agent_id: 접근할 에이전트 ID.
        user: 요청한 사용자.

    Returns:
        DebateAgent — 검증을 통과한 에이전트 모델.

    Raises:
        HTTPException(404): 에이전트가 존재하지 않을 때.
        HTTPException(403): 소유자도 관리자도 아닐 때.
    """
    agent = await service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if agent.owner_id != user.id and user.role not in _ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return agent


def _classify_provider_error(exc: httpx.HTTPStatusError) -> tuple[str, str]:
    """프로바이더 HTTP 에러를 (error_type, user_message)로 변환.

    각 프로바이더 에러 포맷:
      OpenAI    → body["error"]["code"]:   "invalid_api_key" | "model_not_found"
      Anthropic → body["error"]["type"]:   "authentication_error" | "not_found_error"
      Google    → body["error"]["status"]: "UNAUTHENTICATED" | "NOT_FOUND"

    Args:
        exc: httpx HTTP 상태 에러.

    Returns:
        (error_type, user_message) 튜플.
        error_type은 "api_key" | "model" | "other" 중 하나.
    """
    code = exc.response.status_code
    try:
        body = exc.response.json()
    except Exception:
        body = {}

    err = body.get("error", {})
    err_code = str(err.get("code", ""))        # OpenAI: "invalid_api_key" / "model_not_found"
    err_type = err.get("type", "")             # Anthropic: "authentication_error" / "not_found_error"
    err_status = err.get("status", "")         # Google: "UNAUTHENTICATED" / "NOT_FOUND"
    err_msg = err.get("message", "")

    # ── API 키 문제 ────────────────────────────────────────────────────────
    api_key_signals = (
        code == 401
        or err_code == "invalid_api_key"
        or err_type == "authentication_error"
        or err_status == "UNAUTHENTICATED"
    )
    if api_key_signals:
        return "api_key", "API 키가 올바르지 않습니다."

    # ── 모델 문제 ──────────────────────────────────────────────────────────
    model_signals = (
        code == 404
        or err_code == "model_not_found"
        or err_type == "not_found_error"
        or err_status == "NOT_FOUND"
    )
    if model_signals:
        return "model", "모델을 찾을 수 없습니다. 모델 ID를 확인해주세요."

    # ── 권한 거부 (403) — 키는 유효하나 모델 접근 권한 없음 ───────────────
    if code == 403:
        return "api_key", "접근이 거부되었습니다. API 키 권한을 확인해주세요."

    # ── 400 Bad Request — 메시지로 세부 판별 ──────────────────────────────
    if code == 400:
        lower_msg = err_msg.lower()
        if "model" in lower_msg or "not found" in lower_msg:
            return "model", f"모델 오류: {err_msg[:150]}" if err_msg else "모델 ID를 확인해주세요."
        return "api_key", f"잘못된 요청: {err_msg[:150]}" if err_msg else f"API 오류 ({code})"

    return "other", f"API 오류 ({code})" + (f": {err_msg[:120]}" if err_msg else "")


def _agent_response(agent: DebateAgent) -> AgentResponse:
    """AgentResponse에 is_connected 플래그를 추가하여 반환.

    로컬 에이전트인 경우 WSConnectionManager에서 현재 연결 여부를 조회한다.

    Args:
        agent: 응답으로 변환할 DebateAgent 모델.

    Returns:
        AgentResponse — is_connected 필드가 설정된 응답 스키마.
    """
    resp = AgentResponse.model_validate(agent)
    if agent.provider == "local":
        manager = WSConnectionManager.get_instance()
        resp.is_connected = manager.is_connected(agent.id)
    return resp


@router.get("/templates", response_model=list[AgentTemplateResponse])
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """활성 에이전트 템플릿 목록 조회. base_system_prompt는 미노출."""
    service = DebateTemplateService(db)
    templates = await service.list_active_templates()
    return [AgentTemplateResponse.model_validate(t) for t in templates]


class AgentTestRequest(BaseModel):
    """에이전트 API 키/모델 ID 사전 테스트 요청 스키마."""

    provider: str
    model_id: str
    api_key: str = ""


@router.post("/test")
async def test_agent_connection(
    data: AgentTestRequest,
    user: User = Depends(get_current_user),
):
    """API 키·모델 ID 유효성 사전 테스트. DB 저장 없음.

    local/runpod 프로바이더는 플랫폼 키를 사용하므로 항상 ok를 반환한다.

    Args:
        data: 테스트할 provider, model_id, api_key.
        user: 인증된 현재 사용자.

    Returns:
        ok(bool)와 선택적 error_type, error, model_response 필드를 포함한 딕셔너리.
    """
    # local/runpod은 플랫폼 키 사용 — 사용자 측 테스트 불필요
    if data.provider in ("local", "runpod"):
        return {"ok": True}

    if not data.api_key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="API 키를 입력해주세요.")

    from app.services.llm.inference_client import InferenceClient

    client = InferenceClient()
    messages = [{"role": "user", "content": "Say ok"}]

    try:
        result = await asyncio.wait_for(
            client.generate_byok(data.provider, data.model_id, data.api_key, messages, max_tokens=10),
            timeout=15.0,
        )
        return {"ok": True, "model_response": result["content"]}
    except TimeoutError:
        return {"ok": False, "error_type": "other", "error": "응답 시간이 초과되었습니다 (15초)"}
    except httpx.HTTPStatusError as exc:
        error_type, error_msg = _classify_provider_error(exc)
        return {"ok": False, "error_type": error_type, "error": error_msg}
    except ValueError as exc:
        return {"ok": False, "error_type": "other", "error": str(exc)[:200]}
    except Exception as exc:
        return {"ok": False, "error_type": "other", "error": f"테스트 중 오류: {str(exc)[:200]}"}


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 생성. 로그인한 사용자 누구나 가능."""
    service = DebateAgentService(db)
    try:
        agent = await service.create_agent(data, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _agent_response(agent)


@router.get("/me", response_model=list[AgentResponse])
async def get_my_agents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 에이전트 목록 조회."""
    service = DebateAgentService(db)
    agents = await service.get_my_agents(user)
    return [_agent_response(a) for a in agents]


@router.get("/ranking", response_model=AgentRankingListResponse)
async def get_ranking(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, description="에이전트명/소유자명 검색"),
    tier: str | None = Query(None, description="티어 필터"),
    season_id: str | None = Query(None, description="시즌 ID (없으면 누적 랭킹)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ELO 글로벌 랭킹 조회. season_id 지정 시 시즌 랭킹 반환."""
    service = DebateAgentService(db)
    items, total = await service.get_ranking(
        limit=limit, offset=offset, search=search, tier=tier, season_id=season_id
    )
    return {"items": items, "total": total}


@router.get("/ranking/my")
async def get_my_ranking(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 에이전트들의 글로벌 랭킹 순위 조회."""
    service = DebateAgentService(db)
    return await service.get_my_ranking(user)


@router.get("/gallery", response_model=GalleryListResponse)
async def get_agent_gallery(
    sort: str = Query("elo", pattern="^(elo|wins|recent)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공개 에이전트 갤러리 조회."""
    service = DebateAgentService(db)
    items, total = await service.get_gallery(sort=sort, skip=skip, limit=limit)
    return {"items": items, "total": total}


@router.post("/gallery/{agent_id}/clone", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def clone_agent(
    agent_id: str,
    data: CloneRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """공개 에이전트 복제."""
    service = DebateAgentService(db)
    try:
        agent = await service.clone_agent(agent_id, user, data.name)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _agent_response(agent)


@router.get("/season/current")
async def get_current_season(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """현재 활성 시즌 조회."""
    from app.services.debate.season_service import DebateSeasonService

    service = DebateSeasonService(db)
    season = await service.get_current_season()
    if season is None:
        return {"season": None}
    return {
        "season": {
            "id": str(season.id),
            "season_number": season.season_number,
            "title": season.title,
            "start_at": season.start_at,
            "end_at": season.end_at,
            "status": season.status,
        }
    }


@router.get("/season/{season_id}/results")
async def get_season_results(
    season_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """시즌 결과 조회."""
    from app.services.debate.season_service import DebateSeasonService

    service = DebateSeasonService(db)
    items = await service.get_season_results(season_id)
    return {"items": items}


@router.get("/{agent_id}/head-to-head", response_model=HeadToHeadListResponse)
async def get_head_to_head(
    agent_id: str,
    limit: int = Query(5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 간 상대 전적 (H2H) 조회."""
    service = DebateAgentService(db)
    try:
        items = await service.get_head_to_head(agent_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"items": items}


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse | AgentPublicResponse:
    """소유자는 전체 응답, 비소유자는 공개 응답만 반환.
    is_system_prompt_public=True이면 비소유자에게도 최신 버전의 system_prompt 포함.
    follower_count, is_following은 상세 조회에서만 포함 (목록 API N+1 방지).
    """
    from app.services.follow_service import FollowService

    service = DebateAgentService(db)
    agent = await service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    follow_svc = FollowService(db)
    follower_count = await follow_svc.get_follower_count("agent", agent.id)
    is_following = await follow_svc.is_following(user.id, "agent", agent.id)

    if agent.owner_id == user.id:
        resp = _agent_response(agent)
        resp.follower_count = follower_count
        resp.is_following = is_following
        return resp

    resp = AgentPublicResponse.model_validate(agent)
    resp.follower_count = follower_count
    resp.is_following = is_following
    if agent.is_system_prompt_public:
        latest_version = await service.get_latest_version(agent_id)
        if latest_version:
            resp.system_prompt = latest_version.system_prompt
    return resp


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 수정. 프롬프트/커스터마이징 변경 시 새 버전 자동 생성."""
    service = DebateAgentService(db)
    try:
        agent = await service.update_agent(agent_id, data, user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    return _agent_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 삭제. 소유자만 가능(403). 미존재 시 404. 진행 중 매치 있으면 400."""
    service = DebateAgentService(db)
    try:
        await service.delete_agent(agent_id, user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail) from exc


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
async def get_agent_versions(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """버전 히스토리(system_prompt 포함)는 소유자만 조회 가능."""
    service = DebateAgentService(db)
    await _require_agent_access(service, agent_id, user)
    versions = await service.get_agent_versions(agent_id)
    return [AgentVersionResponse.model_validate(v) for v in versions]


@router.get("/{agent_id}/series", response_model=PromotionSeriesResponse | None)
async def get_agent_active_series(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트의 현재 활성 승급전/강등전 시리즈 조회. 없으면 null 반환."""
    from app.services.debate.promotion_service import DebatePromotionService

    agent_service = DebateAgentService(db)
    await _require_agent_access(agent_service, agent_id, user)

    promo_svc = DebatePromotionService(db)
    series = await promo_svc.get_active_series(agent_id)
    if series is None:
        return None
    return PromotionSeriesResponse.model_validate(series)


@router.get("/{agent_id}/series/history", response_model=list[PromotionSeriesResponse])
async def get_agent_series_history(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트의 승급전/강등전 시리즈 이력 조회 (최신 순)."""
    from app.services.debate.promotion_service import DebatePromotionService

    agent_service = DebateAgentService(db)
    await _require_agent_access(agent_service, agent_id, user)

    promo_svc = DebatePromotionService(db)
    history = await promo_svc.get_series_history(agent_id, limit=limit, offset=offset)
    return [PromotionSeriesResponse.model_validate(s) for s in history]
