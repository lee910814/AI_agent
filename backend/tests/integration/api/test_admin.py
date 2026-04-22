import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header

PERSONA_DATA = {
    "persona_key": "admin-test-persona",
    "version": "v1.0",
    "display_name": "Admin Test",
    "system_prompt": "Test persona for admin.",
    "style_rules": {"tone": "formal"},
    "safety_rules": {},
    "visibility": "public",
}

LLM_MODEL_DATA = {
    "provider": "openai",
    "model_id": "gpt-4o-mini",
    "display_name": "GPT-4o Mini",
    "input_cost_per_1m": 0.15,
    "output_cost_per_1m": 0.60,
    "max_context_length": 128000,
}

WEBTOON_DATA = {
    "title": "Tower of God",
    "platform": "naver",
    "genre": ["fantasy", "action"],
    "age_rating": "15+",
}


# ══════════════════════════════════
# Admin Users
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_admin_list_users(client: AsyncClient, test_admin, test_user):
    headers = auth_header(test_admin)
    response = await client.get("/api/admin/users", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2  # test_admin + test_user
    nicknames = [u["nickname"] for u in data["items"]]
    assert "testadmin" in nicknames
    assert "testuser" in nicknames


@pytest.mark.asyncio
async def test_admin_list_users_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/admin/users", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_superadmin_update_user_role(client: AsyncClient, test_superadmin, test_user):
    """superadmin이 역할 변경 가능."""
    headers = auth_header(test_superadmin)
    response = await client.put(
        f"/api/admin/users/{test_user.id}/role",
        json={"role": "admin"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_superadmin_update_user_role_invalid(client: AsyncClient, test_superadmin, test_user):
    headers = auth_header(test_superadmin)
    response = await client.put(
        f"/api/admin/users/{test_user.id}/role",
        json={"role": "godmode"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_superadmin_update_user_role_not_found(client: AsyncClient, test_superadmin):
    headers = auth_header(test_superadmin)
    response = await client.put(
        f"/api/admin/users/{uuid.uuid4()}/role",
        json={"role": "admin"},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_update_user_role_forbidden(client: AsyncClient, test_admin, test_user):
    """일반 admin은 역할 변경 불가 (superadmin 전용)."""
    headers = auth_header(test_admin)
    response = await client.put(
        f"/api/admin/users/{test_user.id}/role",
        json={"role": "admin"},
        headers=headers,
    )
    assert response.status_code == 403


# ── Admin Users: Detail ──


@pytest.mark.asyncio
async def test_admin_get_user_detail(client: AsyncClient, test_admin, test_user):
    """사용자 상세 조회 (관계 카운트 포함)."""
    headers = auth_header(test_admin)
    response = await client.get(f"/api/admin/users/{test_user.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["nickname"] == "testuser"
    assert "credit_balance" in data
    assert data["session_count"] >= 0
    assert data["message_count"] >= 0


@pytest.mark.asyncio
async def test_admin_get_user_detail_not_found(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.get(f"/api/admin/users/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_get_user_detail_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get(f"/api/admin/users/{test_user.id}", headers=headers)
    assert response.status_code == 403


# ── Admin Users: Search & Stats ──


@pytest.mark.asyncio
async def test_admin_list_users_search(client: AsyncClient, test_admin, test_user):
    """닉네임 검색 필터링."""
    headers = auth_header(test_admin)
    response = await client.get("/api/admin/users?search=testuser", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all("testuser" in u["nickname"] for u in data["items"])


@pytest.mark.asyncio
async def test_admin_list_users_has_stats(client: AsyncClient, test_admin, test_user):
    """응답에 stats 필드 포함."""
    headers = auth_header(test_admin)
    response = await client.get("/api/admin/users", headers=headers)
    data = response.json()
    assert "stats" in data
    assert data["stats"]["total_users"] >= 2


# ── Admin Users: Bulk Delete ──


@pytest.mark.asyncio
async def test_superadmin_bulk_delete_users(client: AsyncClient, test_superadmin, db_session):
    """superadmin이 일반 사용자 일괄 삭제."""
    from app.core.auth import get_password_hash
    from app.models.user import User as UserModel

    temp_user = UserModel(
        id=uuid.uuid4(),
        nickname="temp_delete_user",
        password_hash=get_password_hash("testpass"),
        role="user",
        age_group="unverified",
    )
    db_session.add(temp_user)
    await db_session.commit()

    headers = auth_header(test_superadmin)
    response = await client.post(
        "/api/admin/users/bulk-delete",
        json={"user_ids": [str(temp_user.id)]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1


@pytest.mark.asyncio
async def test_superadmin_bulk_delete_skips_admins(client: AsyncClient, test_superadmin, test_admin):
    """admin/superadmin 계정은 삭제되지 않고 skipped_admin_ids에 반환."""
    headers = auth_header(test_superadmin)
    response = await client.post(
        "/api/admin/users/bulk-delete",
        json={"user_ids": [str(test_admin.id)]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 0
    assert str(test_admin.id) in response.json()["skipped_admin_ids"]


@pytest.mark.asyncio
async def test_admin_bulk_delete_forbidden(client: AsyncClient, test_admin, test_user):
    """일반 admin은 삭제 불가 (superadmin 전용)."""
    headers = auth_header(test_admin)
    response = await client.post(
        "/api/admin/users/bulk-delete",
        json={"user_ids": [str(test_user.id)]},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_bulk_delete_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.post(
        "/api/admin/users/bulk-delete",
        json={"user_ids": [str(test_user.id)]},
        headers=headers,
    )
    assert response.status_code == 403


# ══════════════════════════════════
# Admin Personas (Moderation)
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_admin_moderation_queue(client: AsyncClient, test_admin, test_user):
    """pending 페르소나가 모더레이션 대기열에 표시."""
    # test_user가 공개 페르소나 생성 → pending 상태
    user_headers = auth_header(test_user)
    await client.post("/api/personas", json=PERSONA_DATA, headers=user_headers)

    admin_headers = auth_header(test_admin)
    response = await client.get("/api/admin/personas", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(p["moderation_status"] == "pending" for p in data["items"])


@pytest.mark.asyncio
async def test_admin_approve_persona(client: AsyncClient, test_admin, test_user):
    user_headers = auth_header(test_user)
    data = {**PERSONA_DATA, "persona_key": "approve-test"}
    create_resp = await client.post("/api/personas", json=data, headers=user_headers)
    persona_id = create_resp.json()["id"]

    admin_headers = auth_header(test_admin)
    response = await client.put(
        f"/api/admin/personas/{persona_id}/moderation",
        json={"action": "approved"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["moderation_status"] == "approved"
    assert response.json()["is_active"] is True


@pytest.mark.asyncio
async def test_admin_block_persona(client: AsyncClient, test_admin, test_user):
    user_headers = auth_header(test_user)
    data = {**PERSONA_DATA, "persona_key": "block-test"}
    create_resp = await client.post("/api/personas", json=data, headers=user_headers)
    persona_id = create_resp.json()["id"]

    admin_headers = auth_header(test_admin)
    response = await client.put(
        f"/api/admin/personas/{persona_id}/moderation",
        json={"action": "blocked"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["moderation_status"] == "blocked"
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_moderation_invalid_action(client: AsyncClient, test_admin, test_user):
    user_headers = auth_header(test_user)
    data = {**PERSONA_DATA, "persona_key": "invalid-action"}
    create_resp = await client.post("/api/personas", json=data, headers=user_headers)
    persona_id = create_resp.json()["id"]

    admin_headers = auth_header(test_admin)
    response = await client.put(
        f"/api/admin/personas/{persona_id}/moderation",
        json={"action": "invalid"},
        headers=admin_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_moderation_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/admin/personas", headers=headers)
    assert response.status_code == 403


# ══════════════════════════════════
# Admin LLM Models
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_superadmin_register_llm_model(client: AsyncClient, test_superadmin):
    headers = auth_header(test_superadmin)
    response = await client.post("/api/admin/models", json=LLM_MODEL_DATA, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "openai"
    assert data["model_id"] == "gpt-4o-mini"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_superadmin_register_llm_model_duplicate(client: AsyncClient, test_superadmin):
    headers = auth_header(test_superadmin)
    await client.post("/api/admin/models", json=LLM_MODEL_DATA, headers=headers)
    response = await client.post("/api/admin/models", json=LLM_MODEL_DATA, headers=headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_admin_list_llm_models(client: AsyncClient, test_admin, test_superadmin):
    """admin도 목록 조회 가능."""
    sa_headers = auth_header(test_superadmin)
    await client.post("/api/admin/models", json=LLM_MODEL_DATA, headers=sa_headers)

    headers = auth_header(test_admin)
    response = await client.get("/api/admin/models", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_superadmin_update_llm_model(client: AsyncClient, test_superadmin):
    headers = auth_header(test_superadmin)
    create_resp = await client.post("/api/admin/models", json=LLM_MODEL_DATA, headers=headers)
    model_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/admin/models/{model_id}",
        json={"display_name": "GPT-4o Mini Updated", "input_cost_per_1m": 0.10},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "GPT-4o Mini Updated"
    assert response.json()["input_cost_per_1m"] == 0.10


@pytest.mark.asyncio
async def test_superadmin_toggle_llm_model(client: AsyncClient, test_superadmin):
    headers = auth_header(test_superadmin)
    create_resp = await client.post("/api/admin/models", json=LLM_MODEL_DATA, headers=headers)
    model_id = create_resp.json()["id"]
    assert create_resp.json()["is_active"] is True

    response = await client.put(f"/api/admin/models/{model_id}/toggle", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    response = await client.put(f"/api/admin/models/{model_id}/toggle", headers=headers)
    assert response.json()["is_active"] is True


@pytest.mark.asyncio
async def test_admin_register_llm_model_forbidden(client: AsyncClient, test_admin):
    """일반 admin은 모델 등록 불가 (superadmin 전용)."""
    headers = auth_header(test_admin)
    response = await client.post("/api/admin/models", json=LLM_MODEL_DATA, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_llm_models_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/admin/models", headers=headers)
    assert response.status_code == 403


# ══════════════════════════════════
# Admin Content (Webtoons / Episodes / Live2D)
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_admin_create_webtoon(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.post("/api/admin/content/webtoons", json=WEBTOON_DATA, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Tower of God"
    assert data["genre"] == ["fantasy", "action"]
    assert data["total_episodes"] == 0


@pytest.mark.asyncio
async def test_admin_list_webtoons(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    await client.post("/api/admin/content/webtoons", json=WEBTOON_DATA, headers=headers)

    response = await client.get("/api/admin/content/webtoons", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_admin_create_episode(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    webtoon_resp = await client.post("/api/admin/content/webtoons", json=WEBTOON_DATA, headers=headers)
    webtoon_id = webtoon_resp.json()["id"]

    response = await client.post(
        f"/api/admin/content/webtoons/{webtoon_id}/episodes",
        json={"episode_number": 1, "title": "Ball", "summary": "The beginning."},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["episode_number"] == 1
    assert response.json()["webtoon_id"] == webtoon_id


@pytest.mark.asyncio
async def test_admin_create_episode_duplicate(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    webtoon_resp = await client.post("/api/admin/content/webtoons", json=WEBTOON_DATA, headers=headers)
    webtoon_id = webtoon_resp.json()["id"]

    ep_data = {"episode_number": 1, "title": "Ep 1"}
    await client.post(f"/api/admin/content/webtoons/{webtoon_id}/episodes", json=ep_data, headers=headers)
    response = await client.post(f"/api/admin/content/webtoons/{webtoon_id}/episodes", json=ep_data, headers=headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_admin_create_episode_webtoon_not_found(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.post(
        f"/api/admin/content/webtoons/{uuid.uuid4()}/episodes",
        json={"episode_number": 1},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_upload_live2d_model(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.post("/api/admin/content/live2d-models", json={
        "name": "Happy Character",
        "model_path": "/assets/live2d/happy.model3.json",
        "emotion_mappings": {"happy": "motion_01", "sad": "motion_02"},
    }, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Happy Character"
    assert data["created_by"] == str(test_admin.id)


@pytest.mark.asyncio
async def test_admin_content_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.post("/api/admin/content/webtoons", json=WEBTOON_DATA, headers=headers)
    assert response.status_code == 403
