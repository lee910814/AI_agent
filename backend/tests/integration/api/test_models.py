import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LLMModel
from tests.conftest import auth_header


@pytest_asyncio.fixture
async def active_model(db_session: AsyncSession):
    model = LLMModel(
        provider="openai",
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        input_cost_per_1m=0.15,
        output_cost_per_1m=0.60,
        max_context_length=128000,
        is_active=True,
        is_adult_only=False,
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


@pytest_asyncio.fixture
async def adult_model(db_session: AsyncSession):
    model = LLMModel(
        provider="openai",
        model_id="gpt-4o-adult",
        display_name="GPT-4o (Adult)",
        input_cost_per_1m=2.50,
        output_cost_per_1m=10.00,
        max_context_length=128000,
        is_active=True,
        is_adult_only=True,
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


@pytest_asyncio.fixture
async def inactive_model(db_session: AsyncSession):
    model = LLMModel(
        provider="anthropic",
        model_id="claude-old",
        display_name="Claude (Deprecated)",
        input_cost_per_1m=3.00,
        output_cost_per_1m=15.00,
        max_context_length=100000,
        is_active=False,
        is_adult_only=False,
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


# ══════════════════════════════════
# GET /api/models/
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_list_models_shows_active_only(client: AsyncClient, test_user, active_model, inactive_model):
    """비활성 모델은 목록에 표시되지 않는다."""
    headers = auth_header(test_user)
    response = await client.get("/api/models", headers=headers)
    assert response.status_code == 200
    data = response.json()
    model_ids = [m["model_id"] for m in data]
    assert "gpt-4o-mini" in model_ids
    assert "claude-old" not in model_ids


@pytest.mark.asyncio
async def test_list_models_hides_adult_for_unverified(client: AsyncClient, test_user, active_model, adult_model):
    """미인증 사용자에게 성인전용 모델은 노출되지 않는다."""
    headers = auth_header(test_user)
    response = await client.get("/api/models", headers=headers)
    assert response.status_code == 200
    data = response.json()
    model_ids = [m["model_id"] for m in data]
    assert "gpt-4o-mini" in model_ids
    assert "gpt-4o-adult" not in model_ids


@pytest.mark.asyncio
async def test_list_models_shows_adult_for_verified(client: AsyncClient, test_adult_user, active_model, adult_model):
    """성인인증 사용자에게 성인전용 모델도 노출된다."""
    headers = auth_header(test_adult_user)
    response = await client.get("/api/models", headers=headers)
    assert response.status_code == 200
    data = response.json()
    model_ids = [m["model_id"] for m in data]
    assert "gpt-4o-mini" in model_ids
    assert "gpt-4o-adult" in model_ids


@pytest.mark.asyncio
async def test_list_models_unauthorized(client: AsyncClient, active_model):
    response = await client.get("/api/models")
    assert response.status_code in (401, 403)


# ══════════════════════════════════
# PUT /api/models/preferred
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_set_preferred_model_success(client: AsyncClient, test_user, active_model):
    headers = auth_header(test_user)
    response = await client.put(
        "/api/models/preferred",
        json={"model_id": str(active_model.id)},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["model_id"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_set_preferred_model_not_found(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.put(
        "/api/models/preferred",
        json={"model_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_set_preferred_model_inactive_rejected(client: AsyncClient, test_user, inactive_model):
    """비활성 모델은 선호 모델로 설정 불가."""
    headers = auth_header(test_user)
    response = await client.put(
        "/api/models/preferred",
        json={"model_id": str(inactive_model.id)},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_set_preferred_adult_model_blocked_for_unverified(client: AsyncClient, test_user, adult_model):
    """미인증 사용자는 성인전용 모델을 선호 모델로 설정 불가."""
    headers = auth_header(test_user)
    response = await client.put(
        "/api/models/preferred",
        json={"model_id": str(adult_model.id)},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_set_preferred_adult_model_allowed_for_verified(client: AsyncClient, test_adult_user, adult_model):
    """성인인증 사용자는 성인전용 모델 선호 설정 가능."""
    headers = auth_header(test_adult_user)
    response = await client.put(
        "/api/models/preferred",
        json={"model_id": str(adult_model.id)},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["model_id"] == "gpt-4o-adult"
