"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod


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

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this provider is reachable and properly configured.

        Returns:
            True if the provider is ready to accept requests, False otherwise.
        """
