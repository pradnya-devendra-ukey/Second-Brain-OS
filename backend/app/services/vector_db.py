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
    """Generates a single vector embedding (used for query-time search)."""
    return get_embeddings_batch([text])[0]

def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generates embeddings for multiple texts in ONE API call.

    This is the key performance optimisation: instead of N sequential HTTP
    requests (one per chunk), we send all chunks together and get all
    embeddings back in a single round-trip.

    Ollama endpoint: POST /api/embed  { model, input: [str, ...] }
    OpenAI endpoint: embeddings.create(model, input=[str, ...])
    """
    if not texts:
        return []

    if settings.USE_LOCAL_LLM:
        try:
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL}/api/embed",
                json={
                    "model": settings.OLLAMA_EMBEDDING_MODEL,
                    "input": texts          # ← batch of texts, not a single prompt
                },
                timeout=120.0               # larger timeout for big batches
            )
            response.raise_for_status()
            return response.json()["embeddings"]
        except Exception as e:
            raise RuntimeError(f"Failed to generate Ollama batch embeddings: {str(e)}")
    else:
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OpenAI API Key is missing. Please set it in your .env file or switch to local LLM."
            )
        try:
            response = openai_client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=texts                 # ← OpenAI already supports list input
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise RuntimeError(f"Failed to generate OpenAI batch embeddings: {str(e)}")


def init_vector_db():
    """Ensures the document chunks table exists in LanceDB with the correct vector dimensions.

    If the table already exists but was created with a different embedding dimension
    (e.g., switching from OpenAI 1536-dim to Ollama nomic-embed-text 768-dim), the old
    table is automatically dropped and recreated to prevent cast errors on insert.
    """
    # Generate a real embedding to know the expected dimension
    try:
        sample_vector = get_embedding("init")
    except Exception:
        # Fallback defaults: nomic-embed-text=768, OpenAI text-embedding-3-small=1536
        sample_vector = [0.0] * (768 if settings.USE_LOCAL_LLM else 1536)

    expected_dim = len(sample_vector)

    if TABLE_NAME in db.table_names():
        # Check that the existing table has the correct vector dimension
        try:
            existing_table = db.open_table(TABLE_NAME)
            schema = existing_table.schema
            # Find the 'vector' field and read its fixed-size-list length
            for field in schema:
                if field.name == "vector":
                    stored_dim = field.type.list_size
                    if stored_dim != expected_dim:
                        print(
                            f"[vector_db] Dimension mismatch detected: table has {stored_dim}-dim "
                            f"vectors but current embedding model produces {expected_dim}-dim. "
                            f"Dropping and recreating the table."
                        )
                        db.drop_table(TABLE_NAME)
                    break
        except Exception as e:
            print(f"[vector_db] Could not verify table dimensions, will attempt to recreate: {e}")
            try:
                db.drop_table(TABLE_NAME)
            except Exception:
                pass

    if TABLE_NAME not in db.table_names():
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
        # Clean up the dummy seed row immediately
        table = db.open_table(TABLE_NAME)
        table.delete("text = 'init'")


def insert_chunks(doc_id: int, doc_title: str, chunks: list[str]):
    """Embeds and inserts text chunks for a document into LanceDB.

    All chunks are embedded in a SINGLE batch API call, then written to
    LanceDB in one operation. For a 50-page PDF this reduces ~50 sequential
    HTTP round-trips to Ollama/OpenAI down to just 1.
    """
    if not chunks:
        return

    init_vector_db()
    table = db.open_table(TABLE_NAME)

    # Filter out empty chunks before sending to the embedding API
    valid_chunks = [c for c in chunks if c.strip()]
    if not valid_chunks:
        return

    try:
        # One batch call — the core performance fix
        vectors = get_embeddings_batch(valid_chunks)
    except Exception as e:
        print(f"[vector_db] Batch embedding failed for '{doc_title}': {e}")
        raise

    data = [
        {
            "id": str(uuid.uuid4()),
            "doc_id": doc_id,
            "text": chunk,
            "doc_title": doc_title,
            "vector": vector,
        }
        for chunk, vector in zip(valid_chunks, vectors)
    ]

    if data:
        table.add(data)
        print(f"[vector_db] Indexed {len(data)} chunks for '{doc_title}'")


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
        results = table.search(query_vector).limit(top_k).to_list()

        hits = []
        for r in results:
            hits.append({
                "id": r["id"],
                "doc_id": r["doc_id"],
                "text": r["text"],
                "doc_title": r["doc_title"],
                "distance": r.get("_distance", 1.0)
            })
        return hits
    except Exception as e:
        print(f"[vector_db] Error during vector search: {str(e)}")
        return []
