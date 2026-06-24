import json
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.db import get_db
from app.database import models
from app import schemas
from app.services.rag_service import run_rag_stream

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/sessions", response_model=List[schemas.ChatSessionResponse])
def get_sessions(db: Session = Depends(get_db)):
    """Retrieves all chat sessions sorted by creation time."""
    return db.query(models.ChatSession).order_by(models.ChatSession.created_at.desc()).all()

@router.post("/sessions", response_model=schemas.ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(session_in: schemas.ChatSessionCreate, db: Session = Depends(get_db)):
    """Creates a new chat session."""
    session_id = session_in.id or f"session_{models.datetime.datetime.utcnow().timestamp()}"
    title = session_in.title or "New Conversation"
    
    # Check if session exists
    existing = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if existing:
         return existing
         
    db_session = models.ChatSession(id=session_id, title=title)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@router.get("/sessions/{session_id}", response_model=schemas.ChatSessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Retrieves a specific chat session with its messages."""
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Deletes a chat session."""
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    db.delete(session)
    db.commit()
    return None

@router.post("/sessions/{session_id}/stream")
def stream_chat_response(
    session_id: str,
    request: schemas.ChatQueryRequest,
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_gemini_model: Optional[str] = Header(None, alias="X-Gemini-Model"),
    db: Session = Depends(get_db)
):
    print(f"[chat] Received x_gemini_api_key: {x_gemini_api_key}, x_gemini_model: {x_gemini_model}")
    """Streams RAG responses for a user query and saves history to SQLite database."""
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Get previous message history for context
    db_messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.chat_session_id == session_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in db_messages
    ]
    
    # Update the title of the session if it's currently the default
    if session.title == "New Conversation" and len(request.query) > 5:
        session.title = request.query[:30] + "..." if len(request.query) > 30 else request.query
        db.commit()
        
    def event_generator():
        # First save the user message to SQLite
        user_msg = models.ChatMessage(
            chat_session_id=session_id,
            role="user",
            content=request.query
        )
        # Note: we need a separate session/commit because we are yielding in the generator
        db.add(user_msg)
        db.commit()
        
        full_response = ""
        sources_json = None
        
        # Call the RAG stream engine
        for token in run_rag_stream(
            request.query,
            history=history,
            api_key=x_gemini_api_key,
            llm_model=x_gemini_model
        ):
            if token.startswith("[SOURCES]"):
                sources_json = token.replace("[SOURCES]", "")
                yield token
            else:
                full_response += token
                yield token
                
        # Save assistant message to SQLite
        assistant_msg = models.ChatMessage(
            chat_session_id=session_id,
            role="assistant",
            content=full_response,
            sources=sources_json
        )
        db.add(assistant_msg)
        db.commit()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
