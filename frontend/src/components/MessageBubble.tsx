import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage, StructuredResult } from "../types";

interface Props {
  message: ChatMessage;
}

function getFileTypeBadgeClass(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "csv") return "badge-csv";
  if (ext === "json" || ext === "jsonl") return "badge-json";
  if (ext === "xlsx" || ext === "xls") return "badge-xlsx";
  if (ext === "parquet") return "badge-parquet";
  return "badge-default";
}

function StructuredCard({ result }: { result: StructuredResult }) {
  if (!result) return null;

  // Try to render a table
  if (result.type === "table" && result.rows && result.columns) {
    return (
      <div className="structured-card">
        <div className="structured-card-header">
          <span className="structured-card-title">{result.title ?? "Structured Result"}</span>
          {result.confidence !== undefined && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)" }}>
              confidence: {(result.confidence * 100).toFixed(0)}%
            </span>
          )}
        </div>
        <div className="structured-card-body">
          <table>
            <thead>
              <tr>
                {result.columns.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.slice(0, 20).map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j}>{String(cell ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // Fallback: render JSON data as table if it's an array of objects
  if (Array.isArray(result.data) && result.data.length > 0 && typeof result.data[0] === "object") {
    const cols = Object.keys(result.data[0]);
    return (
      <div className="structured-card">
        <div className="structured-card-header">
          <span className="structured-card-title">{result.title ?? result.type?.toUpperCase() ?? "Result"}</span>
        </div>
        <div className="structured-card-body">
          <table>
            <thead>
              <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {result.data.slice(0, 20).map((row: any, i: number) => (
                <tr key={i}>
                  {cols.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return null;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`message-group ${isUser ? "user" : ""}`}>
      <div className={`message-avatar ${isUser ? "user-avatar" : "assistant-avatar"}`}>
        {isUser ? "👤" : "🔬"}
      </div>
      <div className="message-bubble">
        <div className="message-meta">
          {isUser ? "You" : "SmartAnalyst"}&nbsp;·&nbsp;
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>

        <div className={`message-content ${message.isStreaming && !message.content ? "cursor-blink" : ""}`}>
          {/* Status indicator */}
          {message.status && (
            <div className="status-line">{message.status}</div>
          )}

          {/* Markdown content */}
          {message.content ? (
            <div className={message.isStreaming ? "cursor-blink" : ""}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : message.isStreaming && !message.status ? (
            <span style={{ color: "var(--text-muted)" }}>Thinking…</span>
          ) : null}

          {/* Structured results */}
          {message.structuredResults?.map((result, i) => (
            <StructuredCard key={i} result={result} />
          ))}

          {/* Files used footer */}
          {((message.filesAnalyzed && message.filesAnalyzed.length > 0) || message.durationMs) && (
            <div className="files-used">
              {message.filesAnalyzed && message.filesAnalyzed.length > 0 && (
                <>
                  <span className="files-used-label">Files:</span>
                  {message.filesAnalyzed.map((f) => (
                    <span key={f} className={`file-tag ${getFileTypeBadgeClass(f)}`}>
                      {f}
                    </span>
                  ))}
                </>
              )}
              {message.durationMs && (
                <span className="duration-tag">{(message.durationMs / 1000).toFixed(1)}s</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
