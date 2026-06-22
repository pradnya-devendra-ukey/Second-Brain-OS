import os
import uuid
# pyrefly: ignore [missing-import]
import lancedb
import httpx
from openai import OpenAI
from app.config import settings

# Initialize OpenAI client if api key is provided
openai_client = None
if settings.OPENAI_API_KEY:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Connect to LanceDB
db = lancedb.connect(settings.LANCEDB_DIR)
TABLE_NAME = "document_chunks"

def get_embedding(text: str) -> list[float]:
    """Generates vector embedding for the given text using OpenAI or Ollama."""
    if settings.USE_LOCAL_LLM:
        # Call Ollama embedding API
        try:
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                json={
                    "model": settings.OLLAMA_EMBEDDING_MODEL,
                    "prompt": text
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            raise RuntimeError(f"Failed to generate Ollama embeddings: {str(e)}")
    else:
        # Call OpenAI embedding API
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API Key is missing. Please set it in your .env file or switch to local LLM.")
        try:
            response = openai_client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise RuntimeError(f"Failed to generate OpenAI embeddings: {str(e)}")

def init_vector_db():
    """Ensures the document chunks table exists in LanceDB."""
    # LanceDB creates the table automatically on first write if schemas match,
    # but we can explicitly set up or open it.
    if TABLE_NAME not in db.table_names():
        # Create table with a sample schema on write
        # Schema: id, doc_id, text, doc_title, vector
        # Dynamically determine the embedding size by generating a test embedding
        try:
            sample_vector = get_embedding("init")
        except Exception:
            # Fallback defaults: nomic-embed-text=768, OpenAI text-embedding-3-small=1536
            sample_vector = [0.0] * (768 if settings.USE_LOCAL_LLM else 1536)
        db.create_table(
            TABLE_NAME,
            data=[
                {
                    "id": str(uuid.uuid4()),
                    "doc_id": 0,
                    "text": "init",
                    "doc_title": "init",
                    "vector": sample_vector
                }
            ]
        )
        # Clean up the dummy data immediately
        table = db.open_table(TABLE_NAME)
        table.delete("text = 'init'")

def insert_chunks(doc_id: int, doc_title: str, chunks: list[str]):
    """Embeds and inserts text chunks for a document into LanceDB."""
    if not chunks:
        return
        
    init_vector_db()
    table = db.open_table(TABLE_NAME)
    
    data = []
    for chunk in chunks:
        # Avoid empty chunks
        if not chunk.strip():
            continue
        try:
            vector = get_embedding(chunk)
            data.append({
                "id": str(uuid.uuid4()),
                "doc_id": doc_id,
                "text": chunk,
                "doc_title": doc_title,
                "vector": vector
            })
        except Exception as e:
            print(f"Error embedding chunk: {str(e)}")
            continue
            
    if data:
        table.add(data)

def delete_chunks(doc_id: int):
    """Deletes all vector chunks associated with a specific document ID."""
    init_vector_db()
    table = db.open_table(TABLE_NAME)
    table.delete(f"doc_id = {doc_id}")

def search_vector_db(query: str, top_k: int = 5) -> list[dict]:
    """Searches vector database for semantic similarity and returns matches."""
    init_vector_db()
    table = db.open_table(TABLE_NAME)
    
    try:
        query_vector = get_embedding(query)
        # LanceDB search returns a list of dictionaries with matching fields and _distance
        results = table.search(query_vector).limit(top_k).to_list()
        
        # Format results
        hits = []
        for r in results:
            # LanceDB vector columns are returned, but we don't need them in the RAG response
            hits.append({
                "id": r["id"],
                "doc_id": r["doc_id"],
                "text": r["text"],
                "doc_title": r["doc_title"],
                "distance": r.get("_distance", 1.0)
            })
        return hits
    except Exception as e:
        print(f"Error during vector search: {str(e)}")
        return []
