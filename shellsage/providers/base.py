"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base interface that all LLM providers must implement."""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Send a prompt and return the text completion.

        Args:
            system: The system prompt to set context and behavior.
            user: The user message / query.

        Returns:
            The model's text response.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether this provider is reachable and properly configured.

        Returns:
            True if the provider is ready to accept requests, False otherwise.
        """
