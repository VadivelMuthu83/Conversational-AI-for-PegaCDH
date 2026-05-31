import { Plus, MessageSquare, Trash2 } from "lucide-react";
import { useAppStore } from "../stores/appStore";
import type { LLMProvider } from "../types";

export default function Sidebar() {
  const {
    sessions, activeSessionId, llmProvider, isConnected,
    createSession, setActiveSession, deleteSession, setLLMProvider,
  } = useAppStore();

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🔬</div>
          <div>
            <div className="sidebar-logo-text">SmartAnalysis — Conversational AI for Pega CDH</div>
          </div>
          <span className="sidebar-logo-badge">AI</span>
        </div>

        <button className="btn-new-chat" onClick={() => createSession()}>
          <Plus size={14} />
          New Chat
        </button>
      </div>

      <div className="sidebar-section-label">History</div>

      <div className="sidebar-sessions">
        {sessions.length === 0 && (
          <div style={{ padding: "12px 10px", fontSize: 12, color: "var(--text-muted)" }}>
            No chats yet
          </div>
        )}
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`session-item ${session.id === activeSessionId ? "active" : ""}`}
            onClick={() => setActiveSession(session.id)}
          >
            <MessageSquare size={13} style={{ flexShrink: 0, color: "var(--text-muted)" }} />
            <span className="session-title">{session.title}</span>
            <button
              className="session-delete"
              onClick={(e) => {
                e.stopPropagation();
                deleteSession(session.id);
              }}
              title="Delete chat"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <div style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
          LLM Provider
        </div>
        <select
          className="provider-select"
          value={llmProvider}
          onChange={(e) => setLLMProvider(e.target.value as LLMProvider)}
        >
          <option value="anthropic">Anthropic Claude</option>
          <option value="openai">OpenAI GPT-4o</option>
          <option value="gemini">Google Gemini</option>
        </select>

        <div className="status-badge">
          <div className={`status-dot ${isConnected ? "connected" : ""}`} />
          {isConnected ? "Backend connected" : "Backend offline"}
        </div>
      </div>
    </aside>
  );
}
