"use client";

/**
 * Renders untrusted model-generated HTML in a sandboxed iframe.
 *
 * SECURITY MODEL (see docs/architecture.md "Artifact rendering security"):
 *   - DOMPurify strips <script> tags that reference external/unknown origins
 *     and any inline event-handler attributes (onclick=, onerror=, etc).
 *   - The iframe uses sandbox="allow-scripts" WITHOUT "allow-same-origin".
 *     This is the key isolation primitive: scripts can still run (so simple
 *     interactive demos work) but the iframe is treated as an opaque
 *     cross-origin document by the browser, so it CANNOT read/write the
 *     parent page's cookies, localStorage, or DOM, and cannot navigate the
 *     top-level window.
 *   - No "allow-forms" / "allow-top-navigation" — generated forms can't
 *     submit off-page and the artifact can't hijack navigation.
 *   - srcDoc (not src) is used so the content never becomes a fetchable URL.
 */
import DOMPurify from "dompurify";
import { useMemo } from "react";

interface SandboxedIframeProps {
  content: string;
  title: string;
}

export function SandboxedIframe({ content, title }: SandboxedIframeProps) {
  const cleanHtml = useMemo(() => {
    if (typeof window === "undefined") return "";
    return DOMPurify.sanitize(content, {
      WHOLE_DOCUMENT: true,
      ADD_TAGS: ["style"],
      FORBID_TAGS: ["form", "iframe", "object", "embed"],
      FORBID_ATTR: ["onerror", "onload", "onclick", "onmouseover"],
    });
  }, [content]);

  return (
    <div className="flex flex-col h-full border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
      <div className="bg-gray-50 border-b border-gray-200 px-4 py-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-700 tracking-wide uppercase">Artifact: {title}</span>
        <span className="text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
          Sandboxed preview
        </span>
      </div>
      <iframe
        title={title}
        srcDoc={cleanHtml}
        sandbox="allow-scripts"
        className="w-full h-full border-none flex-1 min-h-[400px]"
      />
    </div>
  );
}
