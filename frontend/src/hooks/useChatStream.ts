"use client";

/**
 * Consumes the backend's SSE stream (POST /api/chat) and exposes React state
 * for the in-progress assistant reply, plus a callback for the finished
 * message (with sources + artifact) once the "done" event arrives.
 *
 * Handles three failure modes explicitly instead of leaving the UI hanging:
 *   - network/connection failure before any bytes arrive
 *   - a typed "error" SSE event from the backend (provider down, etc.)
 *   - an unexpected stream close with no "done" event
 */
import { useCallback, useRef, useState } from "react";
import { API_URL, ArtifactPayload, LlmProvider, SourceCitation } from "@/lib/api";

interface StreamResult {
  content: string;
  sources: SourceCitation[];
  artifact: ArtifactPayload | null;
  provider: string;
}

interface UseChatStreamOptions {
  onDone: (result: StreamResult) => void;
  onStatus?: (message: string) => void;
}

export function useChatStream({ onDone, onStatus }: UseChatStreamOptions) {
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (sessionId: string, message: string, mode: "default" | "ship30" | "artifact", provider?: LlmProvider) => {
      setError(null);
      setStreamingText("");
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      let buffer = "";
      let accumulated = "";
      let finished = false;

      try {
        const res = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, message, mode, provider: provider ?? null }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          const body = await res.text().catch(() => "");
          throw new Error(`Chat request failed (${res.status}): ${body.slice(0, 200)}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const events = buffer.split("\n\n");
          buffer = events.pop() ?? "";

          for (const raw of events) {
            const lines = raw.split("\n");
            const eventLine = lines.find((l) => l.startsWith("event: "));
            const dataLine = lines.find((l) => l.startsWith("data: "));
            if (!eventLine || !dataLine) continue;

            const eventType = eventLine.replace("event: ", "").trim();
            const data = JSON.parse(dataLine.replace("data: ", ""));

            if (eventType === "token") {
              accumulated += data.content;
              setStreamingText(accumulated);
            } else if (eventType === "status") {
              onStatus?.(data.message);
            } else if (eventType === "error") {
              setError(data.message);
              finished = true;
            } else if (eventType === "done") {
              finished = true;
              onDone({
                content: accumulated,
                sources: data.sources ?? [],
                artifact: data.artifact ?? null,
                provider: data.provider ?? "ollama",
              });
            }
          }
        }

        if (!finished) {
          setError("Stream ended unexpectedly before completion. Please retry.");
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Unknown error contacting the assistant.");
        }
      } finally {
        setIsStreaming(false);
        setStreamingText("");
      }
    },
    [onDone, onStatus]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { send, cancel, streamingText, isStreaming, error };
}
