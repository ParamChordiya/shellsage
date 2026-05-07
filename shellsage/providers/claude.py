"""Anthropic Claude provider for ShellSage."""

import os
import re
from pathlib import Path
from typing import Iterator

from rich.console import Console

from shellsage.providers.base import LLMProvider

console = Console()

_DEFAULT_MODEL = "claude-sonnet-4-6"

# Regex that matches Anthropic API key values (sk-ant-...) anywhere in a string.
# Used to redact keys from error messages before they are shown to the user or
# written to logs, preventing accidental API key exposure.
_API_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9\-_]{10,}")


def _redact(text: str) -> str:
    """Replace any embedded API key values with a placeholder."""
    return _API_KEY_RE.sub("[REDACTED]", text)


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

    def complete(
        self,
        system: str,
        user: str,
        messages: list[dict] | None = None,
    ) -> str:
        """Call the Claude API and return the assistant's text response."""
        client = self._get_client()
        msgs = messages if messages is not None else [{"role": "user", "content": user}]
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system,
                messages=msgs,
            )
            return message.content[0].text
        except Exception as exc:
            # Bug fix: str(exc) could include the API key if the SDK serialises
            # request headers into the exception.  Redact before re-raising.
            error_str = _redact(str(exc))
            if "authentication" in error_str.lower() or "api_key" in error_str.lower() or "401" in error_str:
                raise RuntimeError(
                    "Anthropic API key is invalid or expired.\n"
                    "Run 'shellsage init' to update your API key."
                ) from exc
            if "timeout" in error_str.lower():
                raise RuntimeError(
                    "Request to Claude API timed out. Check your internet connection."
                ) from exc
            raise RuntimeError(f"Claude API error: {error_str}") from exc

    def stream(
        self,
        system: str,
        user: str,
        messages: list[dict] | None = None,
    ) -> Iterator[str]:
        """Stream response tokens from the Claude API."""
        client = self._get_client()
        msgs = messages if messages is not None else [{"role": "user", "content": user}]
        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=2048,
                system=system,
                messages=msgs,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as exc:
            # Bug fix: redact any embedded API key from error messages.
            error_str = _redact(str(exc))
            if "authentication" in error_str.lower() or "api_key" in error_str.lower() or "401" in error_str:
                raise RuntimeError(
                    "Anthropic API key is invalid or expired.\n"
                    "Run 'shellsage init' to update your API key."
                ) from exc
            if "timeout" in error_str.lower():
                raise RuntimeError(
                    "Request to Claude API timed out. Check your internet connection."
                ) from exc
            raise RuntimeError(f"Claude API error: {error_str}") from exc

    def is_available(self) -> bool:
        """Return True if the API key is valid and the API is reachable."""
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False
