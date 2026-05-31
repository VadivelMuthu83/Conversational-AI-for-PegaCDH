import { useCallback, useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { Send, Square, RefreshCw, Database } from "lucide-react";
import { useAppStore } from "../stores/appStore";
import { streamChat } from "../utils/api";
import type { ChatMessage, StreamChunk } from "../types";
import MessageBubble from "./MessageBubble";
import FilesPanel from "./FilesPanel";

const SUGGESTIONS = [
  "Summarize all files and list key metrics",
  "Compare records across all datasets",
  "What are the top values in each file?",
  "Show me any trends or anomalies in the data",
];

export default function ChatPanel() {
  const {
    getActiveSession, activeSessionId, llmProvider,
    addMessage, updateMessage, appendToMessage, createSession,
  } = useAppStore();

  const session = getActiveSession();
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [showFiles, setShowFiles] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const streamingMsgId = useRef<string | null>(null);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages.length, isStreaming]);

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  };

  const sendMessage = useCallback(async (text?: string) => {
    const messageText = (text ?? input).trim();
    if (!messageText || isStreaming) return;

    let sessionId = activeSessionId;
    if (!sessionId) {
      sessionId = createSession();
    }

    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    // Add user message
    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: "user",
      content: messageText,
      timestamp: new Date(),
    };
    addMessage(sessionId, userMsg);

    // Add placeholder assistant message
    const assistantMsgId = uuidv4();
    streamingMsgId.current = assistantMsgId;
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
      isStreaming: true,
      status: "Planning...",
    };
    addMessage(sessionId, assistantMsg);

    setIsStreaming(true);
    const abort = new AbortController();
    abortRef.current = abort;

    const currentSession = useAppStore.getState().getActiveSession();
    const history = (currentSession?.messages ?? []).filter(
      (m) => m.id !== assistantMsgId
    );

    await streamChat({
      sessionId,
      message: messageText,
      history,
      llmProvider,
      signal: abort.signal,
      onChunk: (chunk: StreamChunk) => {
        if (!sessionId) return;
        if (chunk.type === "text" && chunk.content) {
          appendToMessage(sessionId, assistantMsgId, chunk.content);
          updateMessage(sessionId, assistantMsgId, { status: undefined });
        } else if (chunk.type === "status" && chunk.content) {
          updateMessage(sessionId, assistantMsgId, { status: chunk.content });
        } else if (chunk.type === "structured" && chunk.data) {
          updateMessage(sessionId, assistantMsgId, (prev: any) => ({
            structuredResults: [
              ...((prev as ChatMessage).structuredResults ?? []),
              chunk.data,
            ],
          }));
        } else if (chunk.type === "done" && chunk.data) {
          updateMessage(sessionId, assistantMsgId, {
            filesAnalyzed: chunk.data.files_analyzed ?? [],
            durationMs: chunk.data.duration_ms,
          });
        } else if (chunk.type === "error") {
          updateMessage(sessionId, assistantMsgId, {
            content: `❌ Error: ${chunk.content}`,
            status: undefined,
          });
        }
      },
      onDone: () => {
        if (!sessionId) return;
        updateMessage(sessionId, assistantMsgId, { isStreaming: false, status: undefined });
        setIsStreaming(false);
        streamingMsgId.current = null;
      },
      onError: (err) => {
        if (!sessionId) return;
        updateMessage(sessionId, assistantMsgId, {
          content: `❌ Connection error: ${err}`,
          isStreaming: false,
          status: undefined,
        });
        setIsStreaming(false);
      },
    });
  }, [input, isStreaming, activeSessionId, llmProvider]);

  const stopStreaming = () => {
    abortRef.current?.abort();
    if (activeSessionId && streamingMsgId.current) {
      updateMessage(activeSessionId, streamingMsgId.current, {
        isStreaming: false,
        status: undefined,
      });
    }
    setIsStreaming(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const messages = session?.messages ?? [];
  const isEmpty = messages.length === 0;

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-title">
          {session?.title ?? "New Chat"}
        </div>
        <div className="chat-header-actions">
          <button
            className="btn-icon"
            onClick={() => setShowFiles(!showFiles)}
            title="Toggle files panel"
          >
            <Database size={13} />
            Files
          </button>
        </div>
      </div>

      {/* Main content area */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Messages */}
        <div className="messages-container" style={{ flex: 1 }}>
          {isEmpty ? (
            <div className="empty-state">
              <div className="empty-state-icon">🔬</div>
              <div className="empty-state-title">SmartAnalysis — Conversational AI for Pega CDH</div>
              <div className="empty-state-desc">
                Ask questions about your data files. I'll analyze CSVs, Excel, JSON,
                Parquet, ZIP archives and more — and return structured, tabular answers.
              </div>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="suggestion-chip"
                    onClick={() => sendMessage(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={bottomRef} />
            </>
          )}
        </div>

        {/* Files Panel */}
        {showFiles && <FilesPanel />}
      </div>

      {/* Input */}
      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder="Ask about your data… (Shift+Enter for newline)"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isStreaming}
          />
          {isStreaming ? (
            <button className="send-button stop-button" onClick={stopStreaming} title="Stop">
              <Square size={14} />
            </button>
          ) : (
            <button
              className="send-button"
              onClick={() => sendMessage()}
              disabled={!input.trim()}
              title="Send"
            >
              <Send size={14} />
            </button>
          )}
        </div>
        <div className="input-hint">
          Powered by {llmProvider === "anthropic" ? "Anthropic Claude" : llmProvider === "openai" ? "OpenAI GPT-4o" : "Google Gemini"}
          &nbsp;·&nbsp;files from configured source
        </div>
      </div>
    </div>
  );
}
