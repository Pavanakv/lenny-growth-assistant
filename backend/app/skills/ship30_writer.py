"""
Ship 30 for 30 content skill.

This is a dedicated, structured prompt-builder (not an ad-hoc one-off prompt)
that encodes the specific writing principles from the Ship 30 for 30 method
so the output is consistent regardless of which underlying model runs it:

  - Hook in the first 2-3 lines (curiosity gap / counterintuitive claim)
  - ~1,250 words
  - Skimmable: short paragraphs, H2/H3 headers, bold anchor words in bullets
  - A single concrete, specific takeaway (checklist or framework)
  - Every substantive claim traceable to a retrieved transcript chunk
"""
from typing import Any

SHIP30_SYSTEM_PROMPT = """You are an expert ghostwriter trained in the Ship 30 for 30 \
methodology, writing for The Lenny Growth Assistant. You transform grounded transcript \
knowledge into a single high-retention essay.

Ship 30 for 30 structural rules you must follow exactly:
1. HOOK (first 2-3 lines): open with a counterintuitive product/growth truth, a sharp \
   tension, or a specific outcome promise. Never open with "In this article" or similar \
   throat-clearing.
2. LENGTH: approximately 1,250 words. Do not pad; do not go under 1,000.
3. FORMATTING FOR SKIMMABILITY:
   - Short paragraphs: 1-3 sentences maximum.
   - Clear Markdown H2 (##) and H3 (###) section headers.
   - Bulleted lists where you enumerate more than 2 related items, with a **bold anchor \
     word or phrase** at the start of each bullet.
4. GROUNDING: every specific claim, statistic, or named tactic must come from the \
   provided transcript context. Attribute strategies to the guest/episode they came from \
   inline, e.g. "As [Guest] explained on [Episode]...". If the context is thin on a point \
   you want to make, generalize honestly rather than inventing a source.
5. TAKEAWAY: end with a concrete, numbered checklist or step-by-step framework the reader \
   can apply today — not a vague summary paragraph.

Output plain Markdown only. Do not wrap the essay in an <artifact> tag yourself — the \
calling system handles artifact packaging."""


def build_ship30_prompt(user_query: str, retrieved_chunks: list[dict[str, Any]]) -> str:
    if not retrieved_chunks:
        context_block = (
            "(No transcript context cleared the relevance threshold for this topic. "
            "Say so plainly instead of fabricating guest attributions.)"
        )
    else:
        context_block = "\n\n".join(
            f"--- Episode: {c['episode']} (Guest: {c['guest']}, {c['timestamp']}) ---\n{c['text']}"
            for c in retrieved_chunks
        )

    return (
        f"Transcript context:\n{context_block}\n\n"
        f"Write a Ship 30 for 30-style essay answering / exploring: {user_query}"
    )
