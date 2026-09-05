"""Common interface every LLM provider (local or cloud) must implement.

Keeping this abstraction thin and provider-agnostic is what lets the rest of
the app (retriever, skills, chat endpoint) stay identical regardless of which
model answers the request.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class ProviderUnavailableError(Exception):
    """Raised when a provider cannot serve a request (down, no key, timeout)."""


class BaseLLMProvider(ABC):
    name: str

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        temperature: float = 0.3,
    ) -> AsyncGenerator[str, None]:
        """Yield response text incrementally."""
        raise NotImplementedError
        yield ""  # pragma: no cover - makes this an async generator for type checkers

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return an embedding vector for `text`."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (is_healthy, detail_message). Must never raise."""
        raise NotImplementedError
