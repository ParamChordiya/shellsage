"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Iterator


class LLMProvider(ABC):
    """Base interface that all LLM providers must implement."""

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        messages: list[dict] | None = None,
    ) -> str:
        """Send a prompt and return the text completion.

        Args:
            system: The system prompt to set context and behavior.
            user: The user message / query. Ignored when *messages* is provided.
            messages: Optional full conversation history as a list of
                ``{"role": "user"|"assistant", "content": "..."}`` dicts.
                When supplied, this is sent as-is and *user* is ignored,
                enabling multi-turn conversations.

        Returns:
            The model's text response.
        """

    # Bug fix: stream() was declared @abstractmethod but neither ClaudeProvider
    # nor OllamaProvider implemented it, making both classes uninstantiable.
    # No code path calls stream() today; make it a non-abstract default that
    # subclasses can override when streaming support is added.
    def stream(
        self,
        system: str,
        user: str,
        messages: list[dict] | None = None,
    ) -> Iterator[str]:
        """Stream response tokens as they arrive.

        Default implementation falls back to a single-shot complete() call,
        yielding the entire response as one chunk.  Subclasses may override
        this to provide true token-by-token streaming.

        Args:
            system: The system prompt to set context and behavior.
            user: The user message / query. Ignored when *messages* is provided.
            messages: Optional full conversation history as a list of
                ``{"role": "user"|"assistant", "content": "..."}`` dicts.
                When supplied, this is sent as-is and *user* is ignored,
                enabling multi-turn conversations.

        Yields:
            String chunks of the model's response as they arrive.
        """
        yield self.complete(system, user, messages)

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this provider is reachable and properly configured.

        Returns:
            True if the provider is ready to accept requests, False otherwise.
        """
