"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage } from "@/lib/api";

interface MessageItemProps {
  message: ChatMessage;
  onOpenArtifact?: (artifact: NonNullable<ChatMessage["artifact"]>) => void;
}

export function MessageItem({ message, onOpenArtifact }: MessageItemProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser ? "bg-brand-600 text-white" : "bg-white border border-gray-200 text-gray-800"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <article className="prose prose-sm max-w-none prose-p:my-2 prose-headings:my-2">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </article>
        )}

        {message.artifact && (
          <button
            onClick={() => onOpenArtifact?.(message.artifact!)}
            className="mt-2 text-xs font-medium text-brand-600 border border-brand-200 bg-brand-50 rounded-lg px-3 py-1.5 hover:bg-brand-100"
          >
            📄 View artifact: {message.artifact.title}
          </button>
        )}

        {!isUser && message.sources?.length > 0 && (
          <details className="mt-2 text-xs text-gray-500">
            <summary className="cursor-pointer select-none">
              {message.sources.length} source{message.sources.length > 1 ? "s" : ""}
            </summary>
            <ul className="mt-1 space-y-1">
              {message.sources.map((s, i) => (
                <li key={i} className="border-l-2 border-gray-200 pl-2">
                  <span className="font-medium">{s.episode}</span> — {s.guest}{" "}
                  <span className="text-gray-400">({s.timestamp}, score {s.score.toFixed(2)})</span>
                </li>
              ))}
            </ul>
          </details>
        )}

        {!isUser && message.sources?.length === 0 && (
          <p className="mt-2 text-xs italic text-amber-600">
            ⚠ No transcript sources cleared the relevance threshold for this answer.
          </p>
        )}
      </div>
    </div>
  );
}
