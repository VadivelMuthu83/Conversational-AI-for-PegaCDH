"""
Data models for chat API.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    history: List[Message] = []
    stream: bool = True
    llm_provider: Optional[str] = None  # override global LLM provider


class StructuredResult(BaseModel):
    type: str  # "table" | "json" | "text" | "error"
    data: Any
    title: Optional[str] = None
    files_used: List[str] = []
    confidence: Optional[float] = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
    structured_results: List[StructuredResult] = []
    files_analyzed: List[str] = []
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None


class StreamChunk(BaseModel):
    type: str  # "text" | "structured" | "status" | "error" | "done"
    content: Optional[str] = None
    data: Optional[Any] = None
    session_id: Optional[str] = None
