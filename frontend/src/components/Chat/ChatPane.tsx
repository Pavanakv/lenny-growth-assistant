"use client";

/**
 * Left-hand chat pane: message history, mode toggle (default / Ship 30 for 30
 * / artifact-focused), model selector, streaming bubble, and input box.
 * Explicit UI states for: empty history, streaming, and error (per
 * design.md "Key interaction states").
 */
import { useEffect, useRef, useState } from "react";
import { ArtifactPayload, ChatMessage, LlmProvider } from "@/lib/api";
import { useChatStream } from "@/hooks/useChatStream";
import { MessageItem } from "./MessageItem";
import { ModelSelector } from "./ModelSelector";

interface ChatPaneProps {
  sessionId: string | null;
  anthropicAvailable: boolean;
  onArtifactReady: (artifact: ArtifactPayload) => void;
}

type Mode = "default" | "ship30" | "artifact";

const MODE_LABELS: Record<Mode, string> = {
  default: "Ask",
  ship30: "Ship 30 for 30 essay",
  artifact: "Generate document",
};

export function ChatPane({ sessionId, anthropicAvailable, onArtifactReady }: ChatPaneProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode>("default");
  const [provider, setProvider] = useState<LlmProvider>("ollama");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { send, isStreaming, streamingText, error } = useChatStream({
    onStatus: (msg) => setStatusMessage(msg),
    onDone: ({ content, sources, artifact, provider: usedProvider }) => {
      setStatusMessage(null);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content,
          mode,
          provider: usedProvider,
          sources,
          created_at: new Date().toISOString(),
          artifact,
        },
      ]);
      if (artifact) onArtifactReady(artifact);
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  const handleSend = async () => {
    if (!input.trim() || !sessionId || isStreaming) return;
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
      mode,
      provider,
      sources: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    const toSend = input;
    setInput("");
    await send(sessionId, toSend, mode, provider);
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white">
        <div className="flex gap-1">
          {(Object.keys(MODE_LABELS) as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`text-xs px-3 py-1.5 rounded-full border ${
                mode === m
                  ? "bg-gray-900 text-white border-gray-900"
                  : "border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {MODE_LABELS[m]}
            </button>
          ))}
        </div>
        <ModelSelector provider={provider} onChange={setProvider} anthropicAvailable={anthropicAvailable} />
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && !isStreaming && (
          <div className="h-full flex flex-col items-center justify-center text-center text-gray-400">
            <p className="text-sm max-w-sm">
              Ask a product or growth question grounded in Lenny&apos;s Podcast transcripts, or switch
              to <strong>Ship 30 for 30 essay</strong> mode to turn an answer into a polished essay.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <MessageItem key={m.id} message={m} onOpenArtifact={onArtifactReady} />
        ))}

        {isStreaming && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-2xl px-4 py-3 text-sm bg-white border border-gray-200 text-gray-800">
              {statusMessage && <p className="text-xs text-gray-400 mb-1">{statusMessage}</p>}
              <p className="whitespace-pre-wrap">{streamingText || "…"}</p>
            </div>
          </div>
        )}

        {error && (
          <div className="max-w-[80%] rounded-xl px-4 py-3 text-sm bg-red-50 border border-red-200 text-red-700">
            ⚠ {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-gray-200 bg-white p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={sessionId ? "Ask about product-market fit, growth loops, pricing..." : "Starting session..."}
            disabled={!sessionId}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:bg-gray-100"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || !sessionId || isStreaming}
            className="rounded-xl bg-brand-600 text-white px-4 py-2 text-sm font-medium disabled:opacity-40 hover:bg-brand-700"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
