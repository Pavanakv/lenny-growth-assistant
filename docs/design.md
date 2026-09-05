# Design

## 1. UI/UX principles
1. **Grounding is visible, not implicit.** Every assistant message shows its
   source count. Zero sources is shown as an explicit amber warning, not
   hidden — trust comes from transparency about what the model does and
   doesn't know, not from confident-sounding prose.
2. **The artifact is a first-class object, not a code block.** Generated
   documents/HTML never dump as raw fenced code in the chat; they open in a
   dedicated, persistent side panel the user can copy from or keep browsing
   while continuing the conversation.
3. **The model choice is a visible, reversible setting**, not a hidden
   config flag — the whole point of the dual-model requirement is letting an
   evaluator compare local vs. cloud, so it lives in the main toolbar, not a
   settings modal.
4. **Every async operation has a legible state.** Retrieving, streaming, and
   error are each their own visual state (status line, streaming bubble,
   red error card) — nothing is a silent spinner with no explanation.

## 2. Information architecture
Two-pane layout:
- **Left — Chat pane.** Mode toggle (Ask / Ship 30 for 30 essay / Generate
  document) → model selector → message history → composer.
- **Right — Artifact viewer.** Empty state by default; populates when an
  artifact is produced; persists across turns so the user can keep chatting
  while referencing it.

This mirrors Claude's own Artifacts pattern deliberately, since the brief
asks for a "similar" experience and it is a well-tested mental model for
"conversation on the left produces durable output on the right."

## 3. Key interaction states
| State | What the user sees |
|---|---|
| **Session initializing** | Composer disabled, placeholder text "Starting session..." |
| **Empty chat** | Centered helper text explaining the two modes |
| **Streaming** | A bubble with the in-progress status line ("Retrieving transcripts...") then live token text |
| **Answer with sources** | Assistant bubble + collapsible "N sources" list (episode, guest, timestamp, similarity score) |
| **Answer with zero sources** | Assistant bubble + explicit amber "No transcript sources cleared the relevance threshold" line |
| **Artifact produced** | Inline "📄 View artifact" button in the chat bubble *and* auto-opens the right panel |
| **Provider fallback** | A status line: "Anthropic not configured — using local Ollama model instead." |
| **Stream error** | A red error card in the chat, model/network message surfaced verbatim (not swallowed) |
| **Backend/DB/Ollama degraded** | A dismissible-by-scroll amber banner under the header summarizing `/api/health` |

## 4. Responsive behavior
- **≥ lg breakpoint (1024px+):** side-by-side two-column grid, artifact panel
  always visible (empty-state placeholder when no artifact yet).
- **< lg (tablet/mobile):** single column; the artifact panel is hidden by
  default and the "View artifact" button becomes the way to open it (a
  `Close` button is shown only in this collapsed mode — see
  `ArtifactViewer.tsx`). Given time constraints, this submission implements
  the state logic and the CSS breakpoint but a slide-over/modal transition
  for mobile artifact viewing is the one visual polish item left as a
  documented follow-up rather than built.

## 5. Accessibility considerations
- Semantic elements: `<header>`, `<main>`, `<button>` (not `<div onClick>`)
  throughout.
- Composer supports keyboard submit (`Enter` to send, `Shift+Enter` for
  newline) so the mouse is never required to converse.
- Color is never the only signal: the health banner and source-count warning
  both pair color with explicit text, not just a colored dot.
- Sufficient contrast: body text is `gray-800`/`gray-900` on white/`gray-50`
  backgrounds, meeting WCAG AA for normal text.
- Iframe artifacts carry a `title` attribute for screen readers.
- Known gap (documented, not fixed here): no explicit `aria-live` region on
  the streaming bubble, so screen readers won't announce incoming tokens
  automatically — a real accessibility follow-up for a production version.

## 6. Design decisions and trade-offs
- **Plain Tailwind utility classes, no component library.** Keeps the bundle
  small and every visual decision inspectable directly in the JSX, which
  matters for an evaluator reading the code, at the cost of some visual
  polish a component library would give for free.
- **SSE over WebSockets.** Chat is one-directional (server → client token
  stream) per turn; SSE is simpler to reason about, works over plain HTTP,
  and needs no extra library on either side.
- **Optimistic user-message rendering.** The user's own message appears
  immediately (before the network round-trip completes) so typing feels
  instant; if the request ultimately fails, the error card appears below it
  rather than silently discarding the input.
