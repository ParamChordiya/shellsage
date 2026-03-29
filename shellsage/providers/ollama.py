"""Ollama local LLM provider for ShellSage."""

import requests

from shellsage.providers.base import LLMProvider

_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_MODEL = "llama3.2"

_OLLAMA_HELP = (
    "Ollama is not running or not reachable at {url}.\n\n"
    "To fix this:\n"
    "  macOS:   brew install ollama && ollama serve\n"
    "  Linux:   curl -fsSL https://ollama.com/install.sh | sh && ollama serve\n"
    "  Windows: https://ollama.com/download\n\n"
    "Then pull a model:\n"
    "  ollama pull llama3.2\n\n"
    "Verify it's running:\n"
    "  curl http://localhost:11434/api/tags"
)


class OllamaProvider(LLMProvider):
    """LLM provider backed by a locally running Ollama instance."""

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(self, system: str, user: str) -> str:
        """Call the Ollama /api/chat endpoint and return the assistant text."""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                _OLLAMA_HELP.format(url=self.base_url)
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Request to Ollama timed out after 60 seconds.\n"
                f"The model '{self.model}' may be loading. Try again in a moment."
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            if status == 404:
                raise RuntimeError(
                    f"Model '{self.model}' not found in Ollama.\n"
                    f"Pull it with: ollama pull {self.model}"
                ) from exc
            raise RuntimeError(f"Ollama HTTP error {status}: {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise RuntimeError(f"Unexpected Ollama response format: {exc}") from exc

    def is_available(self) -> bool:
        """Return True if Ollama is reachable at the configured base URL."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False
