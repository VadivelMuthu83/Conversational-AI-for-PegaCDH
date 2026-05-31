export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  structuredResults?: StructuredResult[];
  filesAnalyzed?: string[];
  durationMs?: number;
  status?: string;
}

export interface StructuredResult {
  type: "table" | "json" | "text" | "error";
  title?: string;
  data: any;
  files_used?: string[];
  confidence?: number;
  columns?: string[];
  rows?: any[][];
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
  updatedAt: Date;
}

export interface FileInfo {
  name: string;
  path: string;
  size: number;
  size_human: string;
  last_modified?: string;
  file_type?: string;
  row_count?: number;
  columns?: string[];
}

export interface IndexedFilesResponse {
  total_files: number;
  total_chunks: number;
  files: FileInfo[];
}

export interface StreamChunk {
  type: "text" | "structured" | "status" | "error" | "done";
  content?: string;
  data?: any;
  session_id?: string;
}

export type LLMProvider = "openai" | "anthropic" | "gemini";
