"""Thin wrapper so ingestion scripts and the retriever share one embedding path."""
from app.providers.base import BaseLLMProvider


async def embed_text(provider: BaseLLMProvider, text: str) -> list[float]:
    # Ollama embedding endpoints work best on reasonably short inputs;
    # truncate defensively so a huge chunk never silently fails.
    return await provider.embed(text[:8000])
