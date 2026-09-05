# Agent Transcript 02 — Frontend build and verification

Continuation of the same session, covering the Next.js frontend.

## Plan
1. `package.json` / `tsconfig.json` / Tailwind + PostCSS config / Dockerfile
2. API client (`lib/api.ts`) — typed contracts matching the backend schemas
3. `useChatStream` — hand-rolled SSE parser (no library; the payload shape
   is simple enough that a dependency wasn't justified)
4. Chat components (ChatPane, MessageItem, ModelSelector)
5. Artifact components (ArtifactViewer, SandboxedIframe)
6. `page.tsx` composition + health-check banner
7. Verification

## Verification steps and results
```
npm install                 # clean install, no peer-dep conflicts
npx tsc --noEmit             # PASS — zero type errors
npx next build                # PASS — compiled successfully, 4 static pages generated
```
No failures to correct on the frontend side this session — the one thing
worth flagging is that `next build` auto-appended `.next/types/**/*.ts` to
`tsconfig.json`'s `include` array and added the `next` plugin entry (its
normal first-build behavior). Checked the diff afterward to confirm it did
**not** silently flip `strict` to `false` in the committed file — it stayed
`true` — before treating the build as final and cleaning up `.next/` and
`node_modules/` ahead of packaging the deliverable.

## Design choices made without needing a fix
- No component library (shadcn/ui, MUI, etc.) — plain Tailwind utilities
  only, to keep every visual decision directly readable in the JSX for
  evaluator review (see `docs/design.md` section 6).
- DOMPurify's `FORBID_TAGS`/`FORBID_ATTR` lists were chosen explicitly
  (`form`, `iframe`, `object`, `embed`, inline event handlers) rather than
  relying on DOMPurify's defaults alone, so the security posture is visible
  and auditable directly in `SandboxedIframe.tsx` rather than implicit in a
  library default that could change across versions.
