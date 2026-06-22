from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

# --- Note Schemas ---
class NoteBase(BaseModel):
    title: str
    content: str = ""
    is_file: bool = False
    file_path: Optional[str] = None
    file_type: Optional[str] = None

class NoteCreate(NoteBase):
    pass

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class NoteResponse(NoteBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Link Schemas ---
class LinkCreate(BaseModel):
    source_id: int
    target_id: int

class LinkResponse(BaseModel):
    id: int
    source_id: int
    target_id: int

    class Config:
        from_attributes = True

# --- Graph Schemas ---
class GraphNode(BaseModel):
    id: str  # e.g., "note_1"
    title: str
    is_file: bool
    file_type: Optional[str] = None

class GraphEdge(BaseModel):
    source: str
    target: str

class GraphData(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphEdge]

# --- Chat Schemas ---
class ChatMessageBase(BaseModel):
    role: str
    content: str
    sources: Optional[str] = None

class ChatMessageResponse(ChatMessageBase):
    id: int
    chat_session_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionCreate(BaseModel):
    id: Optional[str] = None  # Frontend generated UUID
    title: Optional[str] = None

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    messages: List[ChatMessageResponse] = []

    class Config:
        from_attributes = True

# --- RAG/Search Schemas ---
class SearchQuery(BaseModel):
    query: str
    top_k: int = 5

class SearchResultItem(BaseModel):
    id: str
    doc_id: int
    text: str
    doc_title: str
    distance: float

class ChatQueryRequest(BaseModel):
    query: str
    chat_session_id: str
