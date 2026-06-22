import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.database import models
from app import schemas
from app.services.document_parser import parse_document, clean_text
from app.services.rag_service import chunk_text
from app.services.vector_db import insert_chunks
from app.routers.notes import parse_and_update_links

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "./uploads"

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=schemas.NoteResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Uploads a PDF, Markdown, or TXT file, parses content, and indexes it into the vector database."""
    # Validate file extension
    filename = file.filename
    _, ext = os.path.splitext(filename)
    ext = ext.lower().lstrip(".")
    
    if ext not in ["pdf", "md", "txt", "markdown"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Only PDF, MD, and TXT files are allowed."
        )
        
    # Check if a document with this title already exists
    title = os.path.splitext(filename)[0]
    existing = db.query(models.Note).filter(models.Note.title == title).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"A document or note named '{title}' already exists."
        )
        
    # Save file to upload directory
    file_path = os.path.join(UPLOAD_DIR, filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save file on server: {str(e)}"
        )
        
    # Parse text from file
    try:
        raw_text = parse_document(file_path, ext)
        cleaned_text = clean_text(raw_text)
    except Exception as e:
        # Clean up file on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse document: {str(e)}"
        )
        
    if not cleaned_text.strip():
        # Clean up file
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail="The document appears to be empty or contains no parseable text."
        )
        
    # Save metadata to SQLite
    db_note = models.Note(
        title=title,
        content=cleaned_text,
        is_file=True,
        file_path=file_path,
        file_type=ext
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    
    # Process wiki links in the document text (in case documents link to other notes)
    parse_and_update_links(db_note, db)
    
    # Process vector embedding
    try:
        chunks = chunk_text(cleaned_text)
        insert_chunks(db_note.id, db_note.title, chunks)
    except Exception as e:
        # Clean up db record on indexing failure
        db.delete(db_note)
        db.commit()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index document in vector store: {str(e)}"
        )
        
    return db_note
