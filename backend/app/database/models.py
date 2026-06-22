import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import relationship
from app.database.db import Base

# Association table for Note tags (many-to-many)
note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", Integer, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_name", String, primary_key=True)
)

class NoteLink(Base):
    __tablename__ = "note_links"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    source = relationship("Note", foreign_keys=[source_id], back_populates="outgoing_links")
    target = relationship("Note", foreign_keys=[target_id], back_populates="incoming_links")

class Note(Base):
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    content = Column(Text, default="")
    
    # Ingestion support (files vs raw notes)
    is_file = Column(Boolean, default=False)
    file_path = Column(String, nullable=True)
    file_type = Column(String, nullable=True)  # 'pdf', 'md', 'txt', etc.
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    tags = relationship("Note", secondary=note_tags, primaryjoin="Note.id==note_tags.c.note_id", backref="notes_with_tag")
    
    outgoing_links = relationship("NoteLink", foreign_keys=[NoteLink.source_id], back_populates="source", cascade="all, delete-orphan")
    incoming_links = relationship("NoteLink", foreign_keys=[NoteLink.target_id], back_populates="target", cascade="all, delete-orphan")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True, index=True)  # UUID or custom string
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)  # JSON-encoded array of source metadata/chunks
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    session = relationship("ChatSession", back_populates="messages")
