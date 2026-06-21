import os
import sys
from pathlib import Path
from typing import List
from pydantic import BaseModel

# Add the project root to python path to import correctly
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from rag.retriever import get_qa_chain, get_vectorstore, get_embeddings_provider
from ingestion.ingest import ingest_documents

app = FastAPI(title="Second Brain OS API", version="1.0.0")

# Enable CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define directories
PDF_DIR = BASE_DIR / "data" / "pdfs"
NOTES_DIR = BASE_DIR / "data" / "notes"

# Pydantic models for chat requests
class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    input: str
    chat_history: List[ChatMessage]

# Helper to query DB status
def query_db_status():
    db_dir = BASE_DIR / "vectordb"
    if not db_dir.exists():
        return False, 0, None
    try:
        store = get_vectorstore()
        count = store._collection.count()
        return True, count, None
    except Exception as e:
        return False, 0, str(e)

# --- API Endpoints ---

@app.get("/api/status")
def get_status():
    """Retrieve database status, chunk counts, and embedding provider."""
    is_ready, count, err = query_db_status()
    try:
        provider = get_embeddings_provider()
    except Exception:
        provider = "local"
        
    return {
        "is_ready": is_ready,
        "chunks_count": count,
        "embedding_provider": provider,
        "error": err
    }

@app.get("/api/documents")
def get_documents():
    """Scan the data directories and list all uploaded PDFs and text/markdown notes."""
    pdf_files = [f.name for f in PDF_DIR.glob("*.pdf")] if PDF_DIR.exists() else []
    notes_files = []
    
    if NOTES_DIR.exists():
        for f in NOTES_DIR.rglob("*"):
            if f.is_file() and f.suffix.lower() in [".txt", ".md"] and f.name != ".gitkeep":
                try:
                    rel_name = str(f.relative_to(NOTES_DIR))
                except ValueError:
                    rel_name = f.name
                notes_files.append(rel_name)
                
    return {
        "pdfs": pdf_files,
        "notes": notes_files
    }

@app.post("/api/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """Save multiple files to local storage and automatically compile/rebuild vector DB index."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    
    save_count = 0
    for file in files:
        if not file.filename:
            continue
            
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in [".pdf", ".txt", ".md"]:
            continue
            
        if file_extension == ".pdf":
            save_path = PDF_DIR / file.filename
        else:
            save_path = NOTES_DIR / file.filename
            
        try:
            content = await file.read()
            with open(save_path, "wb") as f:
                f.write(content)
            save_count += 1
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save {file.filename}: {str(e)}")
            
    if save_count > 0:
        try:
            # Rebuild index automatically using currently active provider
            provider = get_embeddings_provider()
            chunks_count = ingest_documents(clear_db=True, embedding_provider=provider)
            return {"success": True, "chunks_count": chunks_count}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"File saved but indexing failed: {str(e)}")
            
    return {"success": False, "chunks_count": 0}

@app.delete("/api/documents/{name}")
def delete_document(name: str):
    """Delete a document from local storage and automatically rebuild the DB index."""
    file_path = None
    
    if (PDF_DIR / name).exists():
        file_path = PDF_DIR / name
    elif (NOTES_DIR / name).exists():
        file_path = NOTES_DIR / name
    else:
        # Check recursively in notes directory
        for f in NOTES_DIR.rglob(name):
            if f.is_file():
                file_path = f
                break
                
    if not file_path:
        raise HTTPException(status_code=404, detail=f"Document '{name}' not found")
        
    try:
        file_path.unlink()
        
        # Re-index the database cleanly
        provider = get_embeddings_provider()
        chunks_count = ingest_documents(clear_db=True, embedding_provider=provider)
        return {"success": True, "chunks_count": chunks_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete/re-index: {str(e)}")

@app.post("/api/chat")
def chat_query(req: ChatRequest):
    """Query the RAG retrieval pipeline with chat history context."""
    from langchain_core.messages import HumanMessage, AIMessage
    
    # 1. Verify DB is loaded
    is_ready, count, err = query_db_status()
    if not is_ready:
        raise HTTPException(status_code=400, detail=f"Database is not initialized: {err}")
        
    # 2. Build history messages
    chat_history = []
    for msg in req.chat_history:
        if msg.role == "user":
            chat_history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            chat_history.append(AIMessage(content=msg.content))
            
    # 3. Execute query
    try:
        qa_chain = get_qa_chain()
        response = qa_chain.invoke({"input": req.input, "chat_history": chat_history})
        
        result = response.get("answer", "No answer generated.")
        context_docs = response.get("context", [])
        
        sources = []
        for doc in context_docs:
            sources.append({
                "page_content": doc.page_content,
                "metadata": doc.metadata
            })
            
        return {
            "answer": result,
            "sources": sources
        }
    except Exception as e:
        error_msg = str(e)
        if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            google_api_key = os.environ.get("GOOGLE_API_KEY")
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if google_api_key:
                raise HTTPException(
                    status_code=429, 
                    detail="Gemini API Quota Exhausted. The GOOGLE_API_KEY in your .env file is either the default placeholder or has run out of quota. Please update it with a valid API key."
                )
            elif openai_api_key:
                raise HTTPException(
                    status_code=429, 
                    detail="OpenAI API Quota Exhausted. The OPENAI_API_KEY in your .env file has run out of quota or credits. Please update it with a valid API key."
                )
            else:
                raise HTTPException(
                    status_code=429, 
                    detail=f"API Quota Exhausted: {error_msg}"
                )
        elif "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg or "400" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail="Invalid API Key. Please verify the GOOGLE_API_KEY or OPENAI_API_KEY in your .env file."
            )
        raise HTTPException(status_code=500, detail=f"Error processing RAG chain: {error_msg}")

# --- Serve Static Frontend Files ---

@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")

@app.get("/style.css")
def read_css():
    return FileResponse("frontend/style.css")

@app.get("/app.js")
def read_js():
    return FileResponse("frontend/app.js")
