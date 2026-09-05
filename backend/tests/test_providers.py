"""
Provider-layer tests: fallback logic, artifact extraction, ship30 prompt
construction. These use fakes/mocks rather than live Ollama/Anthropic calls
so the suite runs with zero external dependencies (per the deliverable's
"meaningful automated tests" requirement, not an integration smoke test).
"""
import pytest

from app.config import Settings
from app.providers.factory import get_provider
from app.skills.artifact_generator import extract_artifact
from app.skills.ship30_writer import build_ship30_prompt


def test_factory_falls_back_to_ollama_without_anthropic_key():
    settings = Settings(anthropic_api_key="", default_llm_provider="ollama")
    provider, fell_back = get_provider("anthropic", settings)
    assert provider.name == "ollama"
    assert fell_back is True


def test_factory_uses_anthropic_when_key_present():
    settings = Settings(anthropic_api_key="sk-ant-test-key", default_llm_provider="ollama")
    provider, fell_back = get_provider("anthropic", settings)
    assert provider.name == "anthropic"
    assert fell_back is False


def test_factory_defaults_to_settings_when_no_explicit_choice():
    settings = Settings(default_llm_provider="ollama")
    provider, fell_back = get_provider(None, settings)
    assert provider.name == "ollama"
    assert fell_back is False


def test_extract_artifact_returns_none_when_absent():
    reply, artifact = extract_artifact("Just a normal chat reply, no artifact here.")
    assert artifact is None
    assert reply == "Just a normal chat reply, no artifact here."


def test_extract_artifact_parses_markdown_block():
    raw = (
        'Sure, here you go.\n<artifact type="markdown" title="My Doc">\n# Hello\n\nBody text.\n</artifact>'
    )
    reply, artifact = extract_artifact(raw)
    assert artifact is not None
    assert artifact.artifact_type == "markdown"
    assert artifact.title == "My Doc"
    assert "# Hello" in artifact.content
    assert "<artifact" not in reply


def test_extract_artifact_parses_html_block():
    raw = '<artifact type="html" title="Landing">\n<div>hi</div>\n</artifact>'
    reply, artifact = extract_artifact(raw)
    assert artifact.artifact_type == "html"
    assert "<div>hi</div>" in artifact.content
    # Reply falls back to a synthesized description when nothing else remains.
    assert "Landing" in reply


def test_ship30_prompt_notes_missing_context():
    prompt = build_ship30_prompt("How do I find PMF?", retrieved_chunks=[])
    assert "No transcript context" in prompt
    assert "How do I find PMF?" in prompt


def test_ship30_prompt_includes_episode_attribution():
    chunks = [
        {"episode": "Ep 1", "guest": "Jane Doe", "timestamp": "chunk 1/2", "text": "Retention is king."}
    ]
    prompt = build_ship30_prompt("How do I grow?", retrieved_chunks=chunks)
    assert "Ep 1" in prompt
    assert "Jane Doe" in prompt
    assert "Retention is king." in prompt
