import pathlib

p = pathlib.Path('tests/unit/services/test_debate_engine.py')
existing = p.read_text(encoding='utf-8')

# 새 테스트 코드 작성
new_code = r'''

class TestResolveApiKey:
    """_resolve_api_key 함수 테스트."""

    def test_local_provider_returns_empty_string(self):
        """local 에이전트는 빈 문자열을 반환한다."""
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock

        agent = MagicMock()
        agent.provider = "local"
        agent.encrypted_api_key = None

        result = _resolve_api_key(agent)
        assert result == ""

    def test_platform_credits_openai_returns_env_key(self):
        """use_platform_credits=True이고 provider='openai'일 때 settings.openai_api_key를 반환한다."""
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock, patch

        agent = MagicMock()
        agent.provider = "openai"
        agent.use_platform_credits = True
        agent.encrypted_api_key = None

        with patch("app.services.debate.engine.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-platform-openai-key"
            result = _resolve_api_key(agent)
            assert result == "sk-platform-openai-key"

    def test_platform_credits_anthropic_returns_env_key(self):
        """use_platform_credits=True이고 provider='anthropic'일 때 settings.anthropic_api_key를 반환한다."""
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock, patch

        agent = MagicMock()
        agent.provider = "anthropic"
        agent.use_platform_credits = True
        agent.encrypted_api_key = None

        with patch("app.services.debate.engine.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-platform-anthropic-key"
            result = _resolve_api_key(agent)
            assert result == "sk-platform-anthropic-key"

    def test_byok_returns_decrypted_key(self):
        """use_platform_credits=False일 때 encrypted_api_key를 복호화해서 반환한다."""
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock, patch

        agent = MagicMock()
        agent.provider = "openai"
        agent.use_platform_credits = False
        agent.encrypted_api_key = "gAAAAACdef..."

        with patch("app.services.debate.engine.decrypt_api_key") as mock_decrypt:
            mock_decrypt.return_value = "sk-user-own-key"
            result = _resolve_api_key(agent)
            assert result == "sk-user-own-key"
            mock_decrypt.assert_called_once_with("gAAAAACdef...")

    def test_force_platform_ignores_byok(self):
        """force_platform=True이면 encrypted_api_key를 무시하고 플랫폼 키를 반환한다."""
        from app.services.debate.engine import _resolve_api_key
        from unittest.mock import MagicMock, patch

        agent = MagicMock()
        agent.provider = "anthropic"
        agent.use_platform_credits = False
        agent.encrypted_api_key = "gAAAAACdef..."

        with patch("app.services.debate.engine.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-platform-anthropic"
            result = _resolve_api_key(agent, force_platform=True)
            assert result == "sk-platform-anthropic"
'''

p.write_text(existing + new_code, encoding='utf-8')
print("✓ test_debate_engine.py에 TestResolveApiKey 클래스 추가")
