"""Anthropic Claude provider for ShellSage."""

import os
from pathlib import Path

from rich.console import Console

from shellsage.providers.base import LLMProvider

console = Console()

_DEFAULT_MODEL = "claude-sonnet-4-6"


def _load_api_key() -> str | None:
    """Return the Anthropic API key from env or ~/.shellsage/.env."""
    # 1. Environment variable takes priority
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # 2. ~/.shellsage/.env file
    env_path = Path.home() / ".shellsage" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value

    return None


class ClaudeProvider(LLMProvider):
    """LLM provider backed by the Anthropic Claude API."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazily initialise the Anthropic client."""
        if self._client is not None:
            return self._client

        try:
            import anthropic  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "The 'anthropic' package is required for the Claude provider. "
                "Install it with: pip install anthropic"
            ) from exc

        api_key = _load_api_key()
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Set it as an environment variable or run: shellsage init"
            )

        self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def complete(self, system: str, user: str) -> str:
        """Call the Claude API and return the assistant's text response."""
        client = self._get_client()
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return message.content[0].text
        except Exception as exc:
            error_str = str(exc)
            if "authentication" in error_str.lower() or "api_key" in error_str.lower() or "401" in error_str:
                raise RuntimeError(
                    "Anthropic API key is invalid or expired.\n"
                    "Run 'shellsage init' to update your API key."
                ) from exc
            if "timeout" in error_str.lower():
                raise RuntimeError(
                    "Request to Claude API timed out. Check your internet connection."
                ) from exc
            raise RuntimeError(f"Claude API error: {exc}") from exc

    def is_available(self) -> bool:
        """Return True if the API key is valid and the API is reachable."""
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False
