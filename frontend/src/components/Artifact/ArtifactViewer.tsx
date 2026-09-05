"use client";

/**
 * Right-hand panel: renders the current artifact (markdown or html) beside
 * the chat, per the requirement that generated documents render in-app
 * instead of being dumped as raw code or redirected elsewhere.
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArtifactPayload } from "@/lib/api";
import { SandboxedIframe } from "./SandboxedIframe";

interface ArtifactViewerProps {
  artifact: ArtifactPayload | null;
  onClose: () => void;
}

export function ArtifactViewer({ artifact, onClose }: ArtifactViewerProps) {
  if (!artifact) {
    return (
      <div className="hidden lg:flex flex-col items-center justify-center h-full text-gray-400 border-l border-gray-200 bg-white">
        <p className="text-sm">Generated documents and HTML snippets will appear here.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full border-l border-gray-200 bg-white">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">{artifact.type} artifact</p>
          <h2 className="font-semibold text-gray-800">{artifact.title}</h2>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigator.clipboard.writeText(artifact.content)}
            className="text-xs px-3 py-1.5 rounded-md border border-gray-300 hover:bg-gray-50"
          >
            Copy
          </button>
          <button
            onClick={onClose}
            className="text-xs px-3 py-1.5 rounded-md border border-gray-300 hover:bg-gray-50 lg:hidden"
          >
            Close
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {artifact.type === "html" ? (
          <SandboxedIframe content={artifact.content} title={artifact.title} />
        ) : (
          <article className="prose prose-sm max-w-none prose-headings:font-semibold">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{artifact.content}</ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}
