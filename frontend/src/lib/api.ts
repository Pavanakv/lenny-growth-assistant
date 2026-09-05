/**
 * Thin client for the FastAPI backend. Centralizes the base URL (configurable
 * via NEXT_PUBLIC_API_URL, see .env.example) and the SSE parsing logic used
 * by useChatStream.
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type LlmProvider = "ollama" | "anthropic";

export interface SessionSummary {
  id: string;
  title: string;
  llm_provider: LlmProvider;
  created_at: string;
  updated_at: string;
}

export interface SourceCitation {
  episode: string;
  guest: string;
  timestamp: string;
  score: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  mode: string;
  provider: string;
  sources: SourceCitation[];
  created_at: string;
  artifact?: ArtifactPayload | null;
}

export interface ArtifactPayload {
  id?: string;
  type: "markdown" | "html";
  title: string;
  content: string;
}

export interface HealthComponent {
  status: "ok" | "degraded" | "down";
  detail: string;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  database: HealthComponent;
  ollama: HealthComponent;
  anthropic: HealthComponent;
  vector_index: HealthComponent;
}

export async function createSession(provider: LlmProvider): Promise<SessionSummary> {
  const res = await fetch(`${API_URL}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ llm_provider: provider }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/api/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function fetchSession(sessionId: string) {
  const res = await fetch(`${API_URL}/api/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to fetch session: ${res.status}`);
  return res.json();
}
