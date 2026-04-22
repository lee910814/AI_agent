import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header


@pytest_asyncio.fixture
async def test_user_2(db_session: AsyncSession):
    """추가 사용자 (성인인증 테스트용)."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        login_id="testuser2",
        nickname="testuser2",
        password_hash=get_password_hash("testpass"),
        role="user",
        age_group="unverified",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_3(db_session: AsyncSession):
    """추가 사용자 (미성년 거부 테스트용)."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        login_id="testuser3",
        nickname="testuser3",
        password_hash=get_password_hash("testpass"),
        role="user",
        age_group="unverified",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "nickname": "newuser",
        "password": "securepass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_with_email(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "nickname": "emailuser",
        "password": "securepass123",
        "email": "test@example.com",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_register_duplicate_nickname(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "nickname": "dupuser",
        "password": "password1A",
    })
    response = await client.post("/api/auth/register", json={
        "nickname": "dupuser",
        "password": "password2B",
    })
    assert response.status_code == 409
    assert "Nickname already taken" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_missing_password(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "nickname": "nopassuser",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "nickname": "loginuser",
        "password": "mypassword1",
    })
    response = await client.post("/api/auth/login", json={
        "nickname": "loginuser",
        "password": "mypassword1",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "nickname": "wrongpwuser",
        "password": "correct1A",
    })
    response = await client.post("/api/auth/login", json={
        "nickname": "wrongpwuser",
        "password": "wrong",
    })
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post("/api/auth/login", json={
        "nickname": "ghost",
        "password": "noexist",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["nickname"] == "testuser"
    assert data["role"] == "user"
    assert data["age_group"] == "unverified"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient):
    response = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_adult_verify_self_declare_success(client: AsyncClient, test_user):
    """자가선언 성인인증: 만 19세 이상 생년 → 성공."""
    headers = auth_header(test_user)
    response = await client.post(
        "/api/auth/adult-verify",
        json={"method": "self_declare", "birth_year": 1995},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "verified"
    assert data["verified_at"] is not None
    assert data["method"] == "self_declare"


@pytest.mark.asyncio
async def test_adult_verify_phone_success(client: AsyncClient, test_user_2):
    """휴대폰 인증: 올바른 코드 + 전화번호 → 성공."""
    headers = auth_header(test_user_2)
    response = await client.post(
        "/api/auth/adult-verify",
        json={"method": "phone", "phone_number": "01012345678", "code": "123456"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "verified"
    assert data["method"] == "phone"


@pytest.mark.asyncio
async def test_adult_verify_underage_rejected(client: AsyncClient, test_user_3):
    """만 19세 미만 생년 → 403 거부."""
    headers = auth_header(test_user_3)
    response = await client.post(
        "/api/auth/adult-verify",
        json={"method": "self_declare", "birth_year": 2015},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_adult_verify_phone_wrong_code(client: AsyncClient, test_user_3):
    """휴대폰 인증: 잘못된 코드 → 403 거부."""
    headers = auth_header(test_user_3)
    response = await client.post(
        "/api/auth/adult-verify",
        json={"method": "phone", "phone_number": "01012345678", "code": "000000"},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_blocked_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/admin/users", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_allowed_for_admin(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.get("/api/admin/users", headers=headers)
    # 501 (NotImplementedError) 이 아닌 403이 아님을 확인 — 관리자는 통과
    assert response.status_code != 403
