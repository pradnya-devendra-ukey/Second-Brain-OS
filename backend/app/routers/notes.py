import re
import os
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.db import get_db
from app.database import models
from app import schemas
from app.services.vector_db import insert_chunks, delete_chunks
from app.services.rag_service import chunk_text

router = APIRouter(prefix="/notes", tags=["notes"])

def parse_and_update_links(note: models.Note, db: Session):
    """Parses Obsidian-style [[WikiLinks]] in note content and updates relational links."""
    # Delete existing links where this note is the source
    db.query(models.NoteLink).filter(models.NoteLink.source_id == note.id).delete()
    
    # Match [[Note Title]]
    links = re.findall(r"\[\[(.*?)\]\]", note.content)
    
    for link_title in links:
        link_title = link_title.strip()
        if not link_title:
            continue
            
        # Look up target note by title
        target_note = db.query(models.Note).filter(models.Note.title == link_title).first()
        if target_note and target_note.id != note.id:
            new_link = models.NoteLink(source_id=note.id, target_id=target_note.id)
            db.add(new_link)
            
    db.commit()

@router.get("/", response_model=List[schemas.NoteResponse])
def get_notes(db: Session = Depends(get_db)):
    """Retrieves all notes (both written notes and uploaded documents)."""
    return db.query(models.Note).order_by(models.Note.updated_at.desc()).all()

@router.post("/", response_model=schemas.NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    note_in: schemas.NoteCreate,
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    db: Session = Depends(get_db)
):
    """Creates a new note, chunks/embeds its content, and processes links."""
    # Check if title already exists
    existing = db.query(models.Note).filter(models.Note.title == note_in.title).first()
    if existing:
        raise HTTPException(status_code=400, detail="Note with this title already exists")
        
    db_note = models.Note(
        title=note_in.title,
        content=note_in.content,
        is_file=note_in.is_file,
        file_path=note_in.file_path,
        file_type=note_in.file_type
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    
    # Update relational wiki links
    parse_and_update_links(db_note, db)
    
    # Process vector embedding
    if db_note.content.strip():
        chunks = chunk_text(db_note.content)
        insert_chunks(db_note.id, db_note.title, chunks, api_key=x_gemini_api_key)
        
    return db_note

@router.get("/graph", response_model=schemas.GraphData)
def get_graph_data(db: Session = Depends(get_db)):
    """Returns nodes and links for Obsidian-style graph visualization."""
    notes = db.query(models.Note).all()
    links = db.query(models.NoteLink).all()
    
    nodes_data = [
        schemas.GraphNode(
            id=f"note_{note.id}",
            title=note.title,
            is_file=note.is_file,
            file_type=note.file_type
        )
        for note in notes
    ]
    
    links_data = [
        schemas.GraphEdge(
            source=f"note_{link.source_id}",
            target=f"note_{link.target_id}"
        )
        for link in links
    ]
    
    return schemas.GraphData(nodes=nodes_data, links=links_data)

@router.get("/{note_id}", response_model=schemas.NoteResponse)
def get_note(note_id: int, db: Session = Depends(get_db)):
    """Retrieves a single note by ID."""
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note

@router.put("/{note_id}", response_model=schemas.NoteResponse)
def update_note(
    note_id: int,
    note_in: schemas.NoteUpdate,
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    db: Session = Depends(get_db)
):
    """Updates a note, regenerates chunks/embeddings, and updates links."""
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
        
    if note_in.title is not None:
        # Check title uniqueness if it changes
        if note_in.title != note.title:
            existing = db.query(models.Note).filter(models.Note.title == note_in.title).first()
            if existing:
                raise HTTPException(status_code=400, detail="Note with this title already exists")
        note.title = note_in.title
        
    if note_in.content is not None:
        note.content = note_in.content
        
    db.commit()
    db.refresh(note)
    
    # Recalculate wiki links
    parse_and_update_links(note, db)
    
    # Recalculate embeddings
    delete_chunks(note.id)
    if note.content.strip():
        chunks = chunk_text(note.content)
        insert_chunks(note.id, note.title, chunks, api_key=x_gemini_api_key)
        
    return note

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    """Deletes a note, its relational links, its vector embeddings, and physical files on disk."""
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
        
    # 1. Delete vector embeddings from LanceDB
    delete_chunks(note_id)
    
    # 2. Delete the physical file on disk if it exists
    if note.is_file and note.file_path and os.path.exists(note.file_path):
        try:
            os.remove(note.file_path)
        except Exception as e:
            print(f"Error deleting file from disk: {str(e)}")
            
    # 3. Delete database record
    db.delete(note)
    db.commit()
    
    return None

