import type { ChatMessage, StreamChunk, LLMProvider, IndexedFilesResponse } from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

export async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch(`${BASE_URL}/health`);
    return resp.ok;
  } catch {
    return false;
  }
}

export async function getIndexedFiles(): Promise<IndexedFilesResponse> {
  const resp = await fetch(`${BASE_URL}/files/indexed`);
  if (!resp.ok) throw new Error("Failed to fetch indexed files");
  return resp.json();
}

export async function refreshIndex(): Promise<void> {
  const resp = await fetch(`${BASE_URL}/files/refresh`, { method: "POST" });
  if (!resp.ok) throw new Error("Failed to refresh index");
}

export interface StreamChatOptions {
  sessionId: string;
  message: string;
  history: ChatMessage[];
  llmProvider: LLMProvider;
  onChunk: (chunk: StreamChunk) => void;
  onDone: () => void;
  onError: (err: string) => void;
  signal?: AbortSignal;
}

export async function streamChat(opts: StreamChatOptions): Promise<void> {
  const {
    sessionId, message, history, llmProvider,
    onChunk, onDone, onError, signal,
  } = opts;

  const payload = {
    session_id: sessionId,
    message,
    stream: true,
    llm_provider: llmProvider,
    history: history.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp.toISOString(),
    })),
  };

  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err: any) {
    if (err.name === "AbortError") return;
    onError(err.message || "Network error");
    return;
  }

  if (!resp.ok) {
    onError(`Server error: ${resp.status}`);
    return;
  }

  const reader = resp.body?.getReader();
  if (!reader) {
    onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]" || raw === "[CANCELLED]") {
          onDone();
          return;
        }
        try {
          const chunk: StreamChunk = JSON.parse(raw);
          onChunk(chunk);
        } catch {
          // Malformed chunk, skip
        }
      }
    }
  } catch (err: any) {
    if (err.name !== "AbortError") {
      onError(err.message || "Stream error");
    }
  } finally {
    reader.releaseLock();
    onDone();
  }
}
