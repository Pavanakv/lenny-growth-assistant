"use client";

import { LlmProvider } from "@/lib/api";

interface ModelSelectorProps {
  provider: LlmProvider;
  onChange: (p: LlmProvider) => void;
  anthropicAvailable: boolean;
}

/**
 * Makes the active provider visible + switchable in the UI, per the
 * "flexible LLM configuration" requirement. Disables the Anthropic option
 * (with an explanatory tooltip) when no API key is configured server-side,
 * rather than letting the user pick it and silently falling back.
 */
export function ModelSelector({ provider, onChange, anthropicAvailable }: ModelSelectorProps) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-gray-400">Model:</span>
      <div className="inline-flex rounded-full border border-gray-200 p-0.5 bg-gray-50">
        <button
          onClick={() => onChange("ollama")}
          className={`px-3 py-1 rounded-full transition ${
            provider === "ollama" ? "bg-brand-600 text-white" : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          Ollama (local)
        </button>
        <button
          onClick={() => anthropicAvailable && onChange("anthropic")}
          disabled={!anthropicAvailable}
          title={anthropicAvailable ? "" : "Set ANTHROPIC_API_KEY on the backend to enable this"}
          className={`px-3 py-1 rounded-full transition ${
            provider === "anthropic" ? "bg-brand-600 text-white" : "text-gray-600 hover:bg-gray-100"
          } ${!anthropicAvailable ? "opacity-40 cursor-not-allowed" : ""}`}
        >
          Claude (cloud)
        </button>
      </div>
    </div>
  );
}
