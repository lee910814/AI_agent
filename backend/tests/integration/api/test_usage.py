import uuid

import pytest
from httpx import AsyncClient

from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from tests.conftest import auth_header


async def _create_llm_model(db_session) -> LLMModel:
    """테스트용 LLM 모델 생성."""
    model = LLMModel(
        id=uuid.uuid4(),
        provider="openai",
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        input_cost_per_1m=0.15,
        output_cost_per_1m=0.60,
        max_context_length=128000,
        is_active=True,
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


async def _create_usage_logs(db_session, user_id, model_id, count=3):
    """테스트용 사용량 로그 생성."""
    for i in range(count):
        log = TokenUsageLog(
            user_id=user_id,
            llm_model_id=model_id,
            input_tokens=100 * (i + 1),
            output_tokens=50 * (i + 1),
            cost=0.001 * (i + 1),
        )
        db_session.add(log)
    await db_session.commit()


# ── 사용자 사용량 ──


@pytest.mark.asyncio
async def test_get_my_usage_empty(client: AsyncClient, test_user):
    """사용량이 없을 때 0 반환."""
    headers = auth_header(test_user)
    response = await client.get("/api/usage/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_input_tokens"] == 0
    assert data["total_output_tokens"] == 0
    assert data["total_cost"] == 0


@pytest.mark.asyncio
async def test_get_my_usage_with_data(client: AsyncClient, test_user, db_session):
    """사용량 기록 후 요약 확인."""
    model = await _create_llm_model(db_session)
    await _create_usage_logs(db_session, test_user.id, model.id, count=3)

    headers = auth_header(test_user)
    response = await client.get("/api/usage/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # 100+200+300=600, 50+100+150=300
    assert data["total_input_tokens"] == 600
    assert data["total_output_tokens"] == 300
    assert data["daily_input_tokens"] == 600  # 오늘 생성된 로그


@pytest.mark.asyncio
async def test_get_my_usage_history(client: AsyncClient, test_user, db_session):
    model = await _create_llm_model(db_session)
    await _create_usage_logs(db_session, test_user.id, model.id)

    headers = auth_header(test_user)
    response = await client.get("/api/usage/me/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "daily" in data
    assert "by_model_daily" in data
    assert len(data["daily"]) >= 1
    assert "date" in data["daily"][0]
    assert "input_tokens" in data["daily"][0]


@pytest.mark.asyncio
async def test_get_my_usage_isolation(client: AsyncClient, test_user, test_adult_user, db_session):
    """다른 사용자의 사용량이 포함되지 않음."""
    model = await _create_llm_model(db_session)
    await _create_usage_logs(db_session, test_adult_user.id, model.id, count=5)

    headers = auth_header(test_user)
    response = await client.get("/api/usage/me", headers=headers)
    assert response.json()["total_input_tokens"] == 0


# ── 관리자 사용량 ──


@pytest.mark.asyncio
async def test_admin_usage_summary(client: AsyncClient, test_admin, test_user, db_session):
    model = await _create_llm_model(db_session)
    await _create_usage_logs(db_session, test_user.id, model.id, count=2)

    headers = auth_header(test_admin)
    response = await client.get("/api/admin/usage/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"]["input_tokens"] == 300  # 100+200
    assert data["total"]["unique_users"] >= 1
    assert len(data["by_model"]) >= 1
    assert data["by_model"][0]["model_name"] == "GPT-4o Mini"


@pytest.mark.asyncio
async def test_admin_user_usage(client: AsyncClient, test_admin, test_user, db_session):
    model = await _create_llm_model(db_session)
    await _create_usage_logs(db_session, test_user.id, model.id)

    headers = auth_header(test_admin)
    response = await client.get(f"/api/admin/usage/users/{test_user.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "history" in data
    assert data["summary"]["total_input_tokens"] == 600


@pytest.mark.asyncio
async def test_admin_usage_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/admin/usage/summary", headers=headers)
    assert response.status_code == 403
