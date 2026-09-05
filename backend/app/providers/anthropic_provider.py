"""Cloud LLM provider — Anthropic Claude.

Optional. If ANTHROPIC_API_KEY is unset, `factory.get_provider()` never
instantiates this class for the active request path (see factory.py), so the
app runs with zero cloud dependency by default.

Embeddings: Claude does not expose an embeddings endpoint, so when Anthropic
is selected as the chat provider we still use Ollama's embedding model for
retrieval (a documented trade-off — see architecture.md "Embedding strategy").
"""
import logging

import anthropic

from app.providers.base import BaseLLMProvider, ProviderUnavailableError

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, embed_fallback: BaseLLMProvider):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._embed_fallback = embed_fallback

    async def stream_chat(self, messages, system_prompt, temperature=0.3):
        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=2048,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APIConnectionError as exc:
            raise ProviderUnavailableError(f"Could not reach Anthropic API: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderUnavailableError(
                f"Anthropic API error {exc.status_code}: {exc.message}"
            ) from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderUnavailableError("Anthropic request timed out") from exc

    async def embed(self, text: str) -> list[float]:
        # Delegate to the local embedding model — see class docstring.
        return await self._embed_fallback.embed(text)

    async def health_check(self) -> tuple[bool, str]:
        if not self.client.api_key:
            return False, "no API key configured"
        try:
            await self.client.messages.count_tokens(
                model=self.model, messages=[{"role": "user", "content": "ping"}]
            )
            return True, "reachable"
        except Exception as exc:  # noqa: BLE001
            return False, f"unreachable: {exc}"
