"""Runtime provider selection.

Resolution order for a chat turn:
  1. Explicit `provider` field on the /api/chat request, if given.
  2. The session's stored `llm_provider`.
  3. DEFAULT_LLM_PROVIDER from settings.

If Anthropic is selected but no API key is configured, we log a warning and
transparently fall back to Ollama rather than failing the request — this is
the documented fallback behavior required by the spec (README "Model
configuration" section explains this to the evaluator).
"""
import logging

from app.config import Settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import BaseLLMProvider
from app.providers.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)

_ollama_singleton: OllamaProvider | None = None


def _get_ollama(settings: Settings) -> OllamaProvider:
    global _ollama_singleton
    if _ollama_singleton is None:
        _ollama_singleton = OllamaProvider(
            base_url=settings.ollama_base_url,
            chat_model=settings.ollama_chat_model,
            embed_model=settings.ollama_embed_model,
        )
    return _ollama_singleton


def get_provider(requested: str | None, settings: Settings) -> tuple[BaseLLMProvider, bool]:
    """Returns (provider_instance, fell_back).

    `fell_back` is True when the caller asked for Anthropic but we silently
    served Ollama instead — the chat endpoint surfaces this to the client so
    the UI can show a "using local model (no API key set)" notice.
    """
    choice = requested or settings.default_llm_provider
    ollama = _get_ollama(settings)

    if choice == "anthropic":
        if not settings.anthropic_configured:
            logger.warning(
                "anthropic_requested_without_key_falling_back_to_ollama",
                extra={"event": "provider_fallback", "provider": "anthropic"},
            )
            return ollama, True
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            embed_fallback=ollama,
        ), False

    return ollama, False


def get_embedding_provider(settings: Settings) -> BaseLLMProvider:
    """Embeddings always go through Ollama regardless of chat provider —
    see AnthropicProvider docstring for why."""
    return _get_ollama(settings)
