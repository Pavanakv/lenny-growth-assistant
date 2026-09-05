"""Local LLM provider — talks to an Ollama server.

This is the MANDATORY provider for the graded demo. It requires no API key
and no network egress beyond localhost/the ollama container, which keeps
transcript data from ever leaving the machine.
"""
import json
import logging

import httpx

from app.providers.base import BaseLLMProvider, ProviderUnavailableError

logger = logging.getLogger(__name__)

# nomic-embed-text (and most local embedding models) emit 768-dim vectors.
# We keep the DB column at 384 (see db_models.EMBEDDING_DIM) so ingestion
# truncates/pools down to a consistent size regardless of embedding backend —
# documented explicitly in architecture.md as a deliberate simplification.
_TARGET_DIM = 384


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, chat_model: str, embed_model: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.timeout = timeout

    async def stream_chat(self, messages, system_prompt, temperature=0.3):
        payload = {
            "model": self.chat_model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": True,
            "options": {"temperature": temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise ProviderUnavailableError(
                            f"Ollama returned {resp.status_code}: {body[:300]!r}"
                        )
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            break
        except httpx.ConnectError as exc:
            logger.error("ollama_unreachable", extra={"event": "provider_error", "provider": "ollama"})
            raise ProviderUnavailableError(
                f"Could not reach Ollama at {self.base_url}. Is `ollama serve` / the ollama "
                "container running? Falling back is handled by the caller."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"Ollama request timed out after {self.timeout}s") from exc

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.embed_model, "prompt": text}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                resp.raise_for_status()
                vector = resp.json().get("embedding", [])
        except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            raise ProviderUnavailableError(f"Ollama embedding call failed: {exc}") from exc

        return _fit_dim(vector, _TARGET_DIM)

    async def health_check(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    has_chat = any(self.chat_model.split(":")[0] in m for m in models)
                    if not has_chat:
                        return True, f"reachable, but model '{self.chat_model}' not pulled yet"
                    return True, "reachable"
                return False, f"unexpected status {resp.status_code}"
        except Exception as exc:  # noqa: BLE001 - health checks must never raise
            return False, f"unreachable: {exc}"


def _fit_dim(vector: list[float], target: int) -> list[float]:
    """Pad or mean-pool a vector to `target` dimensions so all providers'
    embeddings are comparable in the same pgvector column."""
    if not vector:
        return [0.0] * target
    if len(vector) == target:
        return vector
    if len(vector) > target:
        # Mean-pool down: average consecutive groups.
        factor = len(vector) / target
        return [
            sum(vector[int(i * factor): int((i + 1) * factor)]) / max(1, int((i + 1) * factor) - int(i * factor))
            for i in range(target)
        ]
    return vector + [0.0] * (target - len(vector))
