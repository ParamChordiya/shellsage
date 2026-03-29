"""Tests for LLM provider implementations."""

import os
from unittest.mock import MagicMock, patch

import pytest

from shellsage.providers.base import LLMProvider
from shellsage.providers.claude import ClaudeProvider
from shellsage.providers.ollama import OllamaProvider


class TestProviderInterface:
    def test_claude_implements_base(self):
        assert issubclass(ClaudeProvider, LLMProvider)

    def test_ollama_implements_base(self):
        assert issubclass(OllamaProvider, LLMProvider)

    def test_claude_has_complete_method(self):
        assert callable(getattr(ClaudeProvider, "complete", None))

    def test_claude_has_is_available_method(self):
        assert callable(getattr(ClaudeProvider, "is_available", None))

    def test_ollama_has_complete_method(self):
        assert callable(getattr(OllamaProvider, "complete", None))

    def test_ollama_has_is_available_method(self):
        assert callable(getattr(OllamaProvider, "is_available", None))


class TestOllamaProvider:
    def test_is_available_returns_false_when_unreachable(self):
        provider = OllamaProvider(base_url="http://localhost:19999")
        assert provider.is_available() is False

    def test_is_available_returns_false_on_connection_error(self):
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("connection refused")
            provider = OllamaProvider()
            assert provider.is_available() is False

    def test_is_available_returns_true_when_reachable(self):
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            provider = OllamaProvider()
            assert provider.is_available() is True

    def test_complete_returns_text_on_success(self):
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "message": {"content": '{"steps": []}'}
            }
            mock_post.return_value = mock_response

            provider = OllamaProvider()
            result = provider.complete("system", "user")
            assert result == '{"steps": []}'

    def test_complete_raises_on_connection_error(self):
        import requests

        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError()
            provider = OllamaProvider()
            with pytest.raises(RuntimeError, match="[Oo]llama"):
                provider.complete("system", "user")

    def test_complete_raises_on_model_not_found(self):
        import requests

        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 404
            http_err = requests.exceptions.HTTPError(response=mock_response)
            mock_post.side_effect = http_err
            provider = OllamaProvider(model="nonexistent-model")
            with pytest.raises(RuntimeError, match="nonexistent-model"):
                provider.complete("system", "user")

    def test_default_model_and_url(self):
        provider = OllamaProvider()
        assert provider.model == "llama3.2"
        assert "11434" in provider.base_url


class TestClaudeProvider:
    def test_raises_when_api_key_missing(self):
        # Ensure no key is set
        env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with patch("pathlib.Path.exists", return_value=False):
                provider = ClaudeProvider()
                with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                    provider.complete("system", "user")
        finally:
            if env_backup is not None:
                os.environ["ANTHROPIC_API_KEY"] = env_backup

    def test_is_available_returns_false_when_key_missing(self):
        env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with patch("pathlib.Path.exists", return_value=False):
                provider = ClaudeProvider()
                assert provider.is_available() is False
        finally:
            if env_backup is not None:
                os.environ["ANTHROPIC_API_KEY"] = env_backup

    def test_complete_calls_api_with_correct_model(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_message = MagicMock()
            mock_message.content = [MagicMock(text='{"steps": []}')]
            mock_client.messages.create.return_value = mock_message

            provider = ClaudeProvider(model="claude-sonnet-4-6")
            provider._client = mock_client

            result = provider.complete("system", "user prompt")
            assert result == '{"steps": []}'
            mock_client.messages.create.assert_called_once()
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["model"] == "claude-sonnet-4-6"

    def test_default_model_is_sonnet(self):
        provider = ClaudeProvider()
        assert "sonnet" in provider.model.lower() or "claude" in provider.model.lower()
