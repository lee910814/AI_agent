"""Rate Limiter 단위 테스트. Redis를 mock하여 미들웨어 및 핵심 함수를 검증."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.rate_limit import (
    BYPASS_PATHS,
    RateLimitMiddleware,
    _extract_identifier,
    _get_rate_limit_config,
    _get_route_group,
    check_rate_limit,
)


# ---------------------------------------------------------------------------
# _get_route_group
# ---------------------------------------------------------------------------
class TestGetRouteGroup:
    def test_auth_prefix(self):
        assert _get_route_group("/api/auth/login") == "auth"
        assert _get_route_group("/api/auth/register") == "auth"

    def test_admin_prefix(self):
        assert _get_route_group("/api/admin/users") == "admin"
        assert _get_route_group("/api/admin/models") == "admin"

    def test_general_api_fallback(self):
        assert _get_route_group("/api/personas") == "api"
        assert _get_route_group("/api/usage/me") == "api"
        assert _get_route_group("/api/webtoons") == "api"

    def test_admin_takes_priority_over_auth(self):
        """'/api/admin/auth-something' 같은 경로는 admin으로 분류."""
        assert _get_route_group("/api/admin/auth-settings") == "admin"


# ---------------------------------------------------------------------------
# _get_rate_limit_config
# ---------------------------------------------------------------------------
class TestGetRateLimitConfig:
    def test_auth_tier(self):
        limit, window = _get_rate_limit_config("auth")
        assert limit == 20
        assert window == 60

    def test_api_tier(self):
        limit, window = _get_rate_limit_config("api")
        assert limit == 300
        assert window == 60

    def test_admin_tier(self):
        limit, window = _get_rate_limit_config("admin")
        assert limit == 120
        assert window == 60

    def test_unknown_group_falls_back_to_api(self):
        limit, _ = _get_rate_limit_config("unknown_group")
        assert limit == 300


# ---------------------------------------------------------------------------
# _extract_identifier
# ---------------------------------------------------------------------------
class TestExtractIdentifier:
    def test_extracts_user_id_from_valid_jwt(self):
        from app.core.auth import create_access_token

        token = create_access_token({"sub": "user-uuid-123", "role": "user"})
        request = MagicMock()
        request.headers = {"authorization": f"Bearer {token}"}
        request.client = MagicMock()
        request.client.host = "10.0.0.1"

        result = _extract_identifier(request)
        assert result == "user:user-uuid-123"

    def test_falls_back_to_ip_when_no_auth_header(self):
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        result = _extract_identifier(request)
        assert result == "ip:192.168.1.100"

    def test_falls_back_to_ip_on_invalid_jwt(self):
        request = MagicMock()
        request.headers = {"authorization": "Bearer invalid-token-abc"}
        request.client = MagicMock()
        request.client.host = "10.0.0.5"

        result = _extract_identifier(request)
        assert result == "ip:10.0.0.5"

    def test_falls_back_to_unknown_when_no_client(self):
        request = MagicMock()
        request.headers = {}
        request.client = None

        result = _extract_identifier(request)
        assert result == "ip:unknown"


# ---------------------------------------------------------------------------
# check_rate_limit (with mocked Redis)
# ---------------------------------------------------------------------------
class TestCheckRateLimit:
    def _make_mock_redis(self, zcard_count: int):
        """Redis mock을 생성한다. pipeline()은 동기 호출, execute()는 비동기."""
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore = MagicMock(return_value=mock_pipe)
        mock_pipe.zadd = MagicMock(return_value=mock_pipe)
        mock_pipe.zcard = MagicMock(return_value=mock_pipe)
        mock_pipe.expire = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[0, 1, zcard_count, True])

        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        return mock_redis

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self):
        mock_redis = self._make_mock_redis(zcard_count=5)

        with patch("app.core.rate_limit.redis_client", mock_redis):
            allowed, limit, remaining, reset_at = await check_rate_limit("user:abc", "api")

        assert allowed is True
        assert limit == 300
        assert remaining == 295
        assert reset_at > int(time.time())

    @pytest.mark.asyncio
    async def test_blocks_request_at_limit(self):
        mock_redis = self._make_mock_redis(zcard_count=301)

        with patch("app.core.rate_limit.redis_client", mock_redis):
            allowed, limit, remaining, reset_at = await check_rate_limit("ip:10.0.0.1", "api")

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_exact_limit_is_allowed(self):
        """정확히 limit 개수는 허용 (초과해야 차단)."""
        mock_redis = self._make_mock_redis(zcard_count=20)

        with patch("app.core.rate_limit.redis_client", mock_redis):
            allowed, limit, remaining, _ = await check_rate_limit("user:x", "auth")

        assert allowed is True
        assert limit == 20
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_different_route_groups_have_different_limits(self):
        """auth(20), api(60), debate(120), admin(120) 각각 확인."""

        async def _check(group: str, count: int) -> tuple[bool, int]:
            mock_redis = self._make_mock_redis(zcard_count=count)
            with patch("app.core.rate_limit.redis_client", mock_redis):
                allowed, limit, _, _ = await check_rate_limit("user:test", group)
            return allowed, limit

        # auth: 20 limit, 21 requests → blocked
        allowed, limit = await _check("auth", 21)
        assert not allowed and limit == 20

        # api: 300 limit, 301 requests → blocked
        allowed, limit = await _check("api", 301)
        assert not allowed and limit == 300

        # debate: 120 limit, 100 requests → allowed
        allowed, limit = await _check("debate", 100)
        assert allowed and limit == 120

        # admin: 120 limit, 100 requests → allowed
        allowed, limit = await _check("admin", 100)
        assert allowed and limit == 120


# ---------------------------------------------------------------------------
# RateLimitMiddleware (dispatch logic)
# ---------------------------------------------------------------------------
class TestRateLimitMiddleware:
    def _make_request(self, path: str = "/api/personas", client_host: str = "127.0.0.1", headers: dict = None):
        request = MagicMock()
        request.url = MagicMock()
        request.url.path = path
        request.headers = headers or {}
        request.client = MagicMock()
        request.client.host = client_host
        return request

    @pytest.mark.asyncio
    async def test_health_endpoint_bypasses_rate_limit(self):
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request(path="/health")

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.core.rate_limit.check_rate_limit") as mock_check:
            response = await middleware.dispatch(request, call_next)

        # check_rate_limit은 호출되지 않아야 한다
        mock_check.assert_not_called()
        call_next.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_metrics_endpoint_bypasses_rate_limit(self):
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request(path="/metrics")

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.core.rate_limit.check_rate_limit") as mock_check:
            response = await middleware.dispatch(request, call_next)

        mock_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_rate_limit_headers_on_success(self):
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request()

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        now = int(time.time())
        with patch("app.core.rate_limit.check_rate_limit", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (True, 60, 55, now + 60)
            response = await middleware.dispatch(request, call_next)

        assert response.headers["X-RateLimit-Limit"] == "60"
        assert response.headers["X-RateLimit-Remaining"] == "55"
        assert response.headers["X-RateLimit-Reset"] == str(now + 60)

    @pytest.mark.asyncio
    async def test_returns_429_when_limit_exceeded(self):
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request()
        call_next = AsyncMock()

        now = int(time.time())
        with patch("app.core.rate_limit.check_rate_limit", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (False, 60, 0, now + 60)
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 429
        # call_next은 호출되지 않아야 한다 (요청이 차단됨)
        call_next.assert_not_awaited()
        assert response.headers["X-RateLimit-Limit"] == "60"
        assert response.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_429_response_body_contains_error_details(self):
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request()
        call_next = AsyncMock()

        now = int(time.time())
        with patch("app.core.rate_limit.check_rate_limit", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (False, 60, 0, now + 30)
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 429
        # JSONResponse body 검증
        body = response.body.decode("utf-8")
        assert "Too many requests" in body
        assert "RATE_LIMIT_EXCEEDED" in body

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_redis_failure(self):
        """Redis 장애 시 요청을 허용하고 경고 로그를 남긴다."""
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request()

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with patch("app.core.rate_limit.check_rate_limit", new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = ConnectionError("Redis connection refused")
            response = await middleware.dispatch(request, call_next)

        # 요청이 허용되어야 한다
        call_next.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_disabled_rate_limit_skips_everything(self):
        """rate_limit_enabled=False이면 rate limit 검사를 건너뛴다."""
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request()

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        with (
            patch("app.core.rate_limit.settings") as mock_settings,
            patch("app.core.rate_limit.check_rate_limit") as mock_check,
        ):
            mock_settings.rate_limit_enabled = False
            response = await middleware.dispatch(request, call_next)

        mock_check.assert_not_called()
        call_next.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_auth_route_uses_auth_group(self):
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request(path="/api/auth/login")

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        now = int(time.time())
        with patch("app.core.rate_limit.check_rate_limit", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (True, 20, 19, now + 60)
            await middleware.dispatch(request, call_next)

        # check_rate_limit이 auth 그룹으로 호출되었는지 확인
        call_args = mock_check.call_args
        assert call_args[0][1] == "auth"

    @pytest.mark.asyncio
    async def test_admin_route_uses_admin_group(self):
        middleware = RateLimitMiddleware(app=MagicMock())
        request = self._make_request(path="/api/admin/users")

        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        now = int(time.time())
        with patch("app.core.rate_limit.check_rate_limit", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (True, 120, 119, now + 60)
            await middleware.dispatch(request, call_next)

        call_args = mock_check.call_args
        assert call_args[0][1] == "admin"
