"""
Artifact generation skill.

Detects whether the model's raw response contains an <artifact> block and, if
so, extracts it into a structured (type, title, content) record that the API
persists and the frontend renders in the Artifact Viewer — instead of dumping
raw fenced code into the chat transcript.

Expected model output shape (instructed via ARTIFACT_SYSTEM_PROMPT):
  <artifact type="markdown" title="...">
  ...content...
  </artifact>
"""
import re
from dataclasses import dataclass

ARTIFACT_SYSTEM_PROMPT = """When the user asks you to create a document, report, essay \
export, or a rendered HTML/CSS snippet, wrap ONLY that deliverable in an artifact tag:

<artifact type="markdown" title="Short Descriptive Title">
...full markdown content...
</artifact>

or

<artifact type="html" title="Short Descriptive Title">
...full, self-contained HTML (inline <style>, no external network requests)...
</artifact>

Rules:
- Exactly one artifact per response, only when the user's request calls for a document
  or renderable snippet (not for short conversational answers).
- Everything outside the <artifact> tags is shown as your normal chat reply — keep that
  part brief (1-3 sentences describing what you made).
- HTML artifacts must be fully self-contained: no external <script src> from untrusted
  domains, no fetch()/XHR calls, no forms that submit off-page. The viewer sandboxes and
  strips anything that violates this, so violating it just produces a broken artifact."""

_ARTIFACT_RE = re.compile(
    r'<artifact\s+type="(?P<type>markdown|html)"\s+title="(?P<title>[^"]*)"\s*>'
    r"(?P<content>.*?)</artifact>",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class ExtractedArtifact:
    artifact_type: str
    title: str
    content: str


def extract_artifact(raw_response: str) -> tuple[str, ExtractedArtifact | None]:
    """Returns (chat_reply_text, artifact_or_none).

    chat_reply_text has the <artifact> block stripped out so the chat pane
    never shows raw artifact markup.
    """
    match = _ARTIFACT_RE.search(raw_response)
    if not match:
        return raw_response.strip(), None

    artifact = ExtractedArtifact(
        artifact_type=match.group("type").lower(),
        title=match.group("title").strip() or "Untitled artifact",
        content=match.group("content").strip(),
    )
    chat_reply = (raw_response[: match.start()] + raw_response[match.end() :]).strip()
    if not chat_reply:
        chat_reply = f"Here's your {artifact.artifact_type} artifact: **{artifact.title}**."
    return chat_reply, artifact
