"""토론 에이전트 템플릿 API 통합 테스트."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# 공통 템플릿 픽스처
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_template(db_session: AsyncSession):
    """테스트용 활성 템플릿 fixture."""
    from app.models.debate_agent_template import DebateAgentTemplate

    tmpl = DebateAgentTemplate(
        id=uuid.uuid4(),
        slug="test_template",
        display_name="테스트 템플릿",
        description="통합 테스트용 템플릿",
        icon="test",
        base_system_prompt="당신은 테스트 에이전트입니다.\n\n{customization_block}\n\n성실히 토론하세요.",
        customization_schema={
            "sliders": [
                {"key": "aggression", "label": "공격성", "min": 1, "max": 5, "default": 3,
                 "description": "높을수록 공격적"},
            ],
            "selects": [
                {
                    "key": "tone",
                    "label": "말투",
                    "options": [
                        {"value": "formal", "label": "격식체"},
                        {"value": "neutral", "label": "중립"},
                    ],
                    "default": "neutral",
                }
            ],
            "free_text": {
                "key": "additional_instructions",
                "label": "추가 지시사항",
                "placeholder": "예시",
                "max_length": 200,
            },
        },
        default_values={"aggression": 3, "tone": "neutral"},
        sort_order=1,
        is_active=True,
    )
    db_session.add(tmpl)
    await db_session.commit()
    await db_session.refresh(tmpl)
    return tmpl


@pytest_asyncio.fixture
async def test_inactive_template(db_session: AsyncSession):
    """비활성 템플릿 fixture."""
    from app.models.debate_agent_template import DebateAgentTemplate

    tmpl = DebateAgentTemplate(
        id=uuid.uuid4(),
        slug="inactive_template",
        display_name="비활성 템플릿",
        description="비활성 테스트용",
        base_system_prompt="비활성 프롬프트 {customization_block}",
        customization_schema={"sliders": [], "selects": []},
        default_values={},
        sort_order=99,
        is_active=False,
    )
    db_session.add(tmpl)
    await db_session.commit()
    await db_session.refresh(tmpl)
    return tmpl


# ---------------------------------------------------------------------------
# GET /api/agents/templates — 사용자 템플릿 목록
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_templates_returns_active_only(
    client: AsyncClient, test_user, test_template, test_inactive_template
):
    """GET /templates은 활성 템플릿만 반환한다."""
    response = await client.get("/api/agents/templates", headers=auth_header(test_user))
    assert response.status_code == 200
    data = response.json()
    slugs = [t["slug"] for t in data]
    assert "test_template" in slugs
    assert "inactive_template" not in slugs


@pytest.mark.asyncio
async def test_list_templates_excludes_base_system_prompt(
    client: AsyncClient, test_user, test_template
):
    """사용자 응답에는 base_system_prompt가 포함되지 않는다."""
    response = await client.get("/api/agents/templates", headers=auth_header(test_user))
    assert response.status_code == 200
    for tmpl in response.json():
        assert "base_system_prompt" not in tmpl


@pytest.mark.asyncio
async def test_list_templates_unauthorized(client: AsyncClient):
    """비로그인 사용자는 템플릿 목록을 조회할 수 없다 (403)."""
    response = await client.get("/api/agents/templates")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_templates_includes_schema_and_defaults(
    client: AsyncClient, test_user, test_template
):
    """응답에 customization_schema와 default_values가 포함된다."""
    response = await client.get("/api/agents/templates", headers=auth_header(test_user))
    assert response.status_code == 200
    tmpl = next(t for t in response.json() if t["slug"] == "test_template")
    assert "customization_schema" in tmpl
    assert "default_values" in tmpl
    assert tmpl["default_values"]["aggression"] == 3


# ---------------------------------------------------------------------------
# POST /api/agents — 템플릿 기반 에이전트 생성
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_agent_with_template(client: AsyncClient, test_user, test_template):
    """template_id로 에이전트를 생성하면 201을 반환한다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Template Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key",
            "template_id": str(test_template.id),
            "customizations": {"aggression": 4, "tone": "formal"},
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["template_id"] == str(test_template.id)
    assert data["customizations"]["aggression"] == 4
    assert data["customizations"]["tone"] == "formal"


@pytest.mark.asyncio
async def test_create_agent_with_template_uses_default_customizations(
    client: AsyncClient, test_user, test_template
):
    """customizations 없이 template_id만 넣으면 기본값으로 에이전트가 생성된다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Default Customization Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key",
            "template_id": str(test_template.id),
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["customizations"]["aggression"] == 3  # default_values
    assert data["customizations"]["tone"] == "neutral"


@pytest.mark.asyncio
async def test_create_agent_with_invalid_customization_returns_422(
    client: AsyncClient, test_user, test_template
):
    """유효하지 않은 커스터마이징 값은 422를 반환한다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Invalid Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key",
            "template_id": str(test_template.id),
            "customizations": {"aggression": 99},  # max=5 초과
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_agent_with_invalid_template_id_returns_422(
    client: AsyncClient, test_user
):
    """존재하지 않는 template_id는 422를 반환한다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Ghost Template Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key",
            "template_id": str(uuid.uuid4()),
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_agent_with_inactive_template_returns_422(
    client: AsyncClient, test_user, test_inactive_template
):
    """비활성 템플릿으로 에이전트 생성 시 422를 반환한다."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Inactive Template Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key",
            "template_id": str(test_inactive_template.id),
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_byok_agent_still_works(client: AsyncClient, test_user):
    """기존 BYOK 방식 에이전트 생성은 여전히 동작한다 (하위 호환)."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "BYOK Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key-123",
            "system_prompt": "You are a skilled debater.",
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["template_id"] is None


@pytest.mark.asyncio
async def test_create_local_agent_still_works(client: AsyncClient, test_user):
    """기존 로컬 에이전트 생성은 여전히 동작한다 (하위 호환)."""
    response = await client.post(
        "/api/agents",
        json={
            "name": "Local Agent",
            "provider": "local",
            "model_id": "custom",
        },
        headers=auth_header(test_user),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "local"
    assert data["template_id"] is None


# ---------------------------------------------------------------------------
# PUT /api/agents/{id} — 커스터마이징 업데이트
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_agent_customizations_creates_new_version(
    client: AsyncClient, test_user, test_template, db_session
):
    """커스터마이징 변경 시 새 버전이 자동 생성된다."""
    # 에이전트 생성
    create_resp = await client.post(
        "/api/agents",
        json={
            "name": "Update Test Agent",
            "provider": "openai",
            "model_id": "gpt-4o",
            "api_key": "sk-key",
            "template_id": str(test_template.id),
            "customizations": {"aggression": 2, "tone": "neutral"},
        },
        headers=auth_header(test_user),
    )
    assert create_resp.status_code == 201
    agent_id = create_resp.json()["id"]

    # 커스터마이징 변경
    update_resp = await client.put(
        f"/api/agents/{agent_id}",
        json={"customizations": {"aggression": 5, "tone": "formal"}},
        headers=auth_header(test_user),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["customizations"]["aggression"] == 5

    # 버전 이력 확인
    versions_resp = await client.get(
        f"/api/agents/{agent_id}/versions",
        headers=auth_header(test_user),
    )
    assert len(versions_resp.json()) == 2


# ---------------------------------------------------------------------------
# 관리자 템플릿 CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_list_templates_includes_inactive(
    client: AsyncClient, test_admin, test_template, test_inactive_template
):
    """관리자는 비활성 템플릿도 조회할 수 있다."""
    response = await client.get(
        "/api/admin/debate/templates", headers=auth_header(test_admin)
    )
    assert response.status_code == 200
    slugs = [t["slug"] for t in response.json()]
    assert "test_template" in slugs
    assert "inactive_template" in slugs


@pytest.mark.asyncio
async def test_admin_list_templates_includes_base_system_prompt(
    client: AsyncClient, test_admin, test_template
):
    """관리자 응답에는 base_system_prompt가 포함된다."""
    response = await client.get(
        "/api/admin/debate/templates", headers=auth_header(test_admin)
    )
    assert response.status_code == 200
    for t in response.json():
        assert "base_system_prompt" in t


@pytest.mark.asyncio
async def test_admin_get_template_detail(
    client: AsyncClient, test_admin, test_template
):
    """관리자는 템플릿 상세를 조회할 수 있다."""
    response = await client.get(
        f"/api/admin/debate/templates/{test_template.id}",
        headers=auth_header(test_admin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "test_template"
    assert "base_system_prompt" in data


@pytest.mark.asyncio
async def test_superadmin_create_template(client: AsyncClient, test_superadmin):
    """슈퍼관리자는 새 템플릿을 생성할 수 있다."""
    response = await client.post(
        "/api/admin/debate/templates",
        json={
            "slug": "new_template",
            "display_name": "새 템플릿",
            "description": "새로 만든 템플릿",
            "base_system_prompt": "당신은 새 에이전트입니다.\n\n{customization_block}",
            "customization_schema": {"sliders": [], "selects": []},
            "default_values": {},
            "sort_order": 10,
            "is_active": True,
        },
        headers=auth_header(test_superadmin),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "new_template"
    assert "base_system_prompt" in data


@pytest.mark.asyncio
async def test_admin_cannot_create_template(client: AsyncClient, test_admin):
    """일반 관리자는 템플릿을 생성할 수 없다 (403)."""
    response = await client.post(
        "/api/admin/debate/templates",
        json={
            "slug": "admin_template",
            "display_name": "관리자 템플릿",
            "base_system_prompt": "프롬프트 {customization_block}",
            "customization_schema": {},
            "default_values": {},
        },
        headers=auth_header(test_admin),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_access_admin_templates(client: AsyncClient, test_user):
    """일반 사용자는 관리자 템플릿 엔드포인트에 접근할 수 없다 (403)."""
    response = await client.get(
        "/api/admin/debate/templates", headers=auth_header(test_user)
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_update_template(
    client: AsyncClient, test_superadmin, test_template
):
    """슈퍼관리자는 템플릿을 수정할 수 있다."""
    response = await client.patch(
        f"/api/admin/debate/templates/{test_template.id}",
        json={"display_name": "수정된 템플릿", "is_active": False},
        headers=auth_header(test_superadmin),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "수정된 템플릿"
    assert data["is_active"] is False
