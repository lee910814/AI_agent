"""단일 세션 강제 기능 단위 테스트. Redis를 mock하여 JTI 기반 세션 관리를 검증."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.auth import (
    clear_user_session,
    create_access_token,
    decode_access_token,
    get_user_session_jti,
    set_user_session,
)


# ---------------------------------------------------------------------------
# set_user_session
# ---------------------------------------------------------------------------
class TestSetUserSession:
    @pytest.mark.asyncio
    async def test_stores_jti_with_ttl(self):
        mock_redis = AsyncMock()
        with patch("app.core.redis.redis_client", mock_redis):
            await set_user_session("user-1", "jti-abc", 3600)
        mock_redis.setex.assert_called_once_with("user_session:user-1", 3600, "jti-abc")

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_raise(self):
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis down")
        with patch("app.core.redis.redis_client", mock_redis):
            # 예외가 전파되지 않고 warning만 로깅해야 함
            await set_user_session("user-1", "jti-abc", 3600)


# ---------------------------------------------------------------------------
# get_user_session_jti
# ---------------------------------------------------------------------------
class TestGetUserSessionJti:
    @pytest.mark.asyncio
    async def test_returns_stored_jti(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"jti-abc"
        with patch("app.core.redis.redis_client", mock_redis):
            result = await get_user_session_jti("user-1")
        assert result == "jti-abc"

    @pytest.mark.asyncio
    async def test_returns_none_when_key_missing(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        with patch("app.core.redis.redis_client", mock_redis):
            result = await get_user_session_jti("user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_redis_failure(self):
        """Redis 장애 시 None 반환(fail-open) — 서비스 중단 방지."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis down")
        with patch("app.core.redis.redis_client", mock_redis):
            result = await get_user_session_jti("user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_decodes_bytes_value(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"jti-xyz"
        with patch("app.core.redis.redis_client", mock_redis):
            result = await get_user_session_jti("user-1")
        assert result == "jti-xyz"

    @pytest.mark.asyncio
    async def test_handles_string_value(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "jti-xyz"  # 이미 str인 경우
        with patch("app.core.redis.redis_client", mock_redis):
            result = await get_user_session_jti("user-1")
        assert result == "jti-xyz"


# ---------------------------------------------------------------------------
# clear_user_session
# ---------------------------------------------------------------------------
class TestClearUserSession:
    @pytest.mark.asyncio
    async def test_deletes_key(self):
        mock_redis = AsyncMock()
        with patch("app.core.redis.redis_client", mock_redis):
            await clear_user_session("user-1")
        mock_redis.delete.assert_called_once_with("user_session:user-1")

    @pytest.mark.asyncio
    async def test_redis_failure_does_not_raise(self):
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = Exception("Redis down")
        with patch("app.core.redis.redis_client", mock_redis):
            await clear_user_session("user-1")  # 예외 전파 없어야 함


# ---------------------------------------------------------------------------
# create_access_token + jti 포함 여부
# ---------------------------------------------------------------------------
class TestCreateAccessTokenWithJti:
    def test_jti_included_in_payload(self):
        token = create_access_token({"sub": "user-1", "jti": "test-jti"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["jti"] == "test-jti"

    def test_no_jti_when_not_provided(self):
        """이전 코드와의 하위 호환 — jti 없이도 토큰 생성 가능."""
        token = create_access_token({"sub": "user-1"})
        payload = decode_access_token(token)
        assert payload is not None
        assert "jti" not in payload


# ---------------------------------------------------------------------------
# 단일 세션 시나리오: 새 로그인이 기존 세션을 무효화
# ---------------------------------------------------------------------------
class TestSingleSessionFlow:
    @pytest.mark.asyncio
    async def test_new_login_overwrites_previous_jti(self):
        """새 로그인 시 Redis에 새 JTI 저장 → 이전 JTI 무효화."""
        mock_redis = AsyncMock()
        stored = {}

        async def fake_setex(key, ttl, val):
            stored[key] = val

        async def fake_get(key):
            return stored.get(key, None)

        mock_redis.setex.side_effect = fake_setex
        mock_redis.get.side_effect = fake_get

        with patch("app.core.redis.redis_client", mock_redis):
            # 첫 번째 로그인
            await set_user_session("user-1", "jti-device-a", 3600)
            assert await get_user_session_jti("user-1") == "jti-device-a"

            # 두 번째 로그인 (다른 기기)
            await set_user_session("user-1", "jti-device-b", 3600)
            current = await get_user_session_jti("user-1")

        # 최신 JTI만 유효
        assert current == "jti-device-b"

    @pytest.mark.asyncio
    async def test_logout_clears_session(self):
        """로그아웃 시 세션 JTI 삭제 → 이후 조회 시 None."""
        mock_redis = AsyncMock()
        stored = {"user_session:user-1": "jti-abc"}

        async def fake_get(key):
            return stored.get(key)

        async def fake_delete(key):
            stored.pop(key, None)

        mock_redis.get.side_effect = fake_get
        mock_redis.delete.side_effect = fake_delete

        with patch("app.core.redis.redis_client", mock_redis):
            assert await get_user_session_jti("user-1") == "jti-abc"
            await clear_user_session("user-1")
            assert await get_user_session_jti("user-1") is None
