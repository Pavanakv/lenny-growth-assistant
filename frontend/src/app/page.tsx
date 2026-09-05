"use client";

/**
 * Top-level page: creates a session on mount, checks backend health (and
 * surfaces a banner if the DB/Ollama are down instead of a silently broken
 * chat), and lays out the two-pane chat + artifact viewer.
 */
import { useEffect, useState } from "react";
import { ArtifactPayload, HealthResponse, createSession, fetchHealth } from "@/lib/api";
import { ChatPane } from "@/components/Chat/ChatPane";
import { ArtifactViewer } from "@/components/Artifact/ArtifactViewer";

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [artifact, setArtifact] = useState<ArtifactPayload | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealthError("Cannot reach the backend API. Is it running?"));

    createSession("ollama")
      .then((s) => setSessionId(s.id))
      .catch(() => setHealthError("Cannot reach the backend API. Is it running?"));
  }, []);

  const showDegradedBanner = health && health.status !== "ok";

  return (
    <main className="h-screen w-screen flex flex-col">
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-lg">🌱</span>
          <h1 className="font-semibold text-gray-800">Lenny Growth Assistant</h1>
        </div>
        {health && (
          <span
            className={`text-xs px-2 py-1 rounded-full ${
              health.status === "ok"
                ? "bg-emerald-50 text-emerald-700"
                : health.status === "degraded"
                ? "bg-amber-50 text-amber-700"
                : "bg-red-50 text-red-700"
            }`}
          >
            {health.status === "ok" ? "All systems ready" : `System ${health.status}`}
          </span>
        )}
      </header>

      {(healthError || showDegradedBanner) && (
        <div className="bg-amber-50 border-b border-amber-200 text-amber-800 text-xs px-4 py-2">
          {healthError ||
            `DB: ${health?.database.status} · Ollama: ${health?.ollama.status} · Vector index: ${health?.vector_index.status}. ` +
              "Some features may not work until these are healthy — see README troubleshooting."}
        </div>
      )}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_1fr] overflow-hidden">
        <ChatPane
          sessionId={sessionId}
          anthropicAvailable={health?.anthropic.status === "ok"}
          onArtifactReady={setArtifact}
        />
        <ArtifactViewer artifact={artifact} onClose={() => setArtifact(null)} />
      </div>
    </main>
  );
}
