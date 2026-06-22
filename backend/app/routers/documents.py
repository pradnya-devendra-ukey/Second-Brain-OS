import os
import shutil
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.database import models
from app import schemas
from app.services.document_parser import parse_document, clean_text
from app.services.rag_service import chunk_text
from app.services.vector_db import insert_chunks, delete_chunks
from app.routers.notes import parse_and_update_links

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = "./uploads"

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _index_document_bg(doc_id: int, doc_title: str, cleaned_text: str, file_path: str):
    """Background task: chunk the document text and embed into LanceDB.

    Runs AFTER the HTTP response has already been sent to the browser so the
    user is not blocked waiting for potentially slow Ollama/OpenAI calls.
    If indexing fails the document record in SQLite is preserved (user can
    still read the content); only vector search won't surface it.
    """
    try:
        print(f"[bg] Starting indexing for '{doc_title}' …")
        chunks = chunk_text(cleaned_text)
        insert_chunks(doc_id, doc_title, chunks)
        print(f"[bg] Finished indexing '{doc_title}' ({len(chunks)} chunks)")
    except Exception as e:
        print(f"[bg] Indexing failed for '{doc_title}': {e}")


@router.post("/upload", response_model=schemas.NoteResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Uploads a PDF, Markdown, or TXT file, parses content, saves to SQLite,
    and schedules vector indexing as a non-blocking background task.

    The HTTP response is returned as soon as the document is saved to the
    database — embedding happens asynchronously so large files no longer
    cause the upload to time out or stall the UI.
    """
    # ── 1. Validate extension ────────────────────────────────────────────────
    filename = file.filename
    _, ext = os.path.splitext(filename)
    ext = ext.lower().lstrip(".")

    if ext not in ["pdf", "md", "txt", "markdown"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Only PDF, MD, and TXT files are allowed.",
        )

    # ── 2. Check for duplicate title ─────────────────────────────────────────
    title = os.path.splitext(filename)[0]
    existing = db.query(models.Note).filter(models.Note.title == title).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A document or note named '{title}' already exists.",
        )

    # ── 3. Save file to disk ──────────────────────────────────────────────────
    file_path = os.path.join(UPLOAD_DIR, filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save file on server: {str(e)}",
        )

    # ── 4. Parse text from file ───────────────────────────────────────────────
    try:
        raw_text = parse_document(file_path, ext)
        cleaned_text = clean_text(raw_text)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse document: {str(e)}",
        )

    if not cleaned_text.strip():
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail="The document appears to be empty or contains no parseable text.",
        )

    # ── 5. Save metadata to SQLite ────────────────────────────────────────────
    db_note = models.Note(
        title=title,
        content=cleaned_text,
        is_file=True,
        file_path=file_path,
        file_type=ext,
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)

    # Process wiki-links in the document text
    parse_and_update_links(db_note, db)

    # ── 6. Schedule vector indexing in the background ─────────────────────────
    # The response is returned immediately after this line; embedding runs
    # asynchronously without blocking the browser.
    background_tasks.add_task(
        _index_document_bg,
        db_note.id,
        db_note.title,
        cleaned_text,
        file_path,
    )

    return db_note
