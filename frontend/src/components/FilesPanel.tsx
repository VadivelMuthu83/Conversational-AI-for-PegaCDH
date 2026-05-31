import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { getIndexedFiles, refreshIndex } from "../utils/api";
import type { FileInfo } from "../types";

function typeBadgeClass(ft: string | undefined): string {
  const t = (ft ?? "").toLowerCase();
  if (t === "csv") return "badge-csv";
  if (t === "json" || t === "jsonl") return "badge-json";
  if (t === "excel" || t === "xlsx") return "badge-xlsx";
  if (t === "parquet") return "badge-parquet";
  return "badge-default";
}

export default function FilesPanel() {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const resp = await getIndexedFiles();
      setFiles(resp.files);
      setTotalChunks(resp.total_chunks);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshIndex();
      await load();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="files-panel">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div className="files-panel-title">Indexed Files</div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            background: "none", border: "none", color: "var(--text-muted)",
            cursor: "pointer", padding: 4, display: "flex",
          }}
          title="Refresh index"
        >
          <RefreshCw size={13} style={{ animation: refreshing ? "spin 1s linear infinite" : "none" }} />
        </button>
      </div>

      <div style={{
        fontFamily: "var(--font-mono)", fontSize: 10,
        color: "var(--text-muted)", marginBottom: 4,
      }}>
        {files.length} files · {totalChunks} chunks
      </div>

      {loading && (
        <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading…</div>
      )}

      {!loading && files.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6 }}>
          No files indexed yet. Add files to the configured path and refresh.
        </div>
      )}

      {files.map((f, i) => (
        <div className="file-item" key={i}>
          <div className="file-item-name" title={f.name}>{f.name}</div>
          <div className="file-item-meta">
            <span className={`file-type-badge ${typeBadgeClass(f.file_type)}`}>
              {f.file_type ?? f.name.split(".").pop()}
            </span>
            {f.row_count && `${f.row_count.toLocaleString()} rows`}
          </div>
        </div>
      ))}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
