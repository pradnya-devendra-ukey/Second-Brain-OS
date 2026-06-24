import os
import uuid
# pyrefly: ignore [missing-import]
import lancedb
from google import genai
from app.config import settings

# Cache client instances to avoid recreation overhead
_client_cache = {}

def get_client(api_key: str = None) -> genai.Client:
    api_key_stripped = api_key.strip() if (api_key and api_key.strip()) else None
    active_key = api_key_stripped or settings.GEMINI_API_KEY
    if not active_key:
        raise ValueError(
            "Gemini API Key is missing. Please set GEMINI_API_KEY in your .env file or configure it in Settings."
        )
    if active_key not in _client_cache:
        _client_cache[active_key] = genai.Client(api_key=active_key)
    return _client_cache[active_key]

# Connect to LanceDB
db = lancedb.connect(settings.LANCEDB_DIR)
TABLE_NAME = "document_chunks"

def get_embedding(text: str, api_key: str = None, embedding_model: str = None) -> list[float]:
    """Generates a single vector embedding (used for query-time search)."""
    return get_embeddings_batch([text], api_key=api_key, embedding_model=embedding_model)[0]

def get_embeddings_batch(texts: list[str], api_key: str = None, embedding_model: str = None) -> list[list[float]]:
    """Generates embeddings for multiple texts using Gemini.

    Batches requests into groups of at most 100 to respect Gemini API limits.
    """
    if not texts:
        return []

    client = get_client(api_key)
    active_model = embedding_model or settings.EMBEDDING_MODEL

    all_embeddings = []
    chunk_size = 100
    for i in range(0, len(texts), chunk_size):
        batch = texts[i : i + chunk_size]
        try:
            result = client.models.embed_content(
                model=active_model,
                contents=batch,
                config={
                    "output_dimensionality": settings.GEMINI_EMBEDDING_DIMENSION,
                },
            )
            all_embeddings.extend([e.values for e in result.embeddings])
        except Exception as e:
            raise RuntimeError(f"Failed to generate Gemini batch embeddings for slice {i}-{i+chunk_size}: {str(e)}")

    return all_embeddings


def init_vector_db(api_key: str = None, embedding_model: str = None):
    """Ensures the document chunks table exists in LanceDB with the correct vector dimensions.

    If the table already exists but was created with a different embedding dimension
    (e.g., switching from OpenAI 1536-dim to Gemini 768-dim), the old
    table is automatically dropped and recreated to prevent cast errors on insert.
    """
    # Generate a real embedding to know the expected dimension
    try:
        sample_vector = get_embedding("init", api_key=api_key, embedding_model=embedding_model)
    except Exception:
        # Fallback default: Gemini text-embedding-004 = 768 dims
        sample_vector = [0.0] * settings.GEMINI_EMBEDDING_DIMENSION

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


def insert_chunks(doc_id: int, doc_title: str, chunks: list[str], api_key: str = None, embedding_model: str = None):
    """Embeds and inserts text chunks for a document into LanceDB.

    All chunks are embedded in a SINGLE batch API call, then written to
    LanceDB in one operation. For a 50-page PDF this reduces ~50 sequential
    HTTP round-trips down to just 1.
    """
    if not chunks:
        return

    init_vector_db(api_key=api_key, embedding_model=embedding_model)
    table = db.open_table(TABLE_NAME)

    # Filter out empty chunks before sending to the embedding API
    valid_chunks = [c for c in chunks if c.strip()]
    if not valid_chunks:
        return

    try:
        # One batch call — the core performance fix
        vectors = get_embeddings_batch(valid_chunks, api_key=api_key, embedding_model=embedding_model)
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
    if TABLE_NAME in db.table_names():
        table = db.open_table(TABLE_NAME)
        table.delete(f"doc_id = {doc_id}")


def search_vector_db(query: str, top_k: int = 5, api_key: str = None, embedding_model: str = None) -> list[dict]:
    """Searches vector database for semantic similarity and returns matches."""
    init_vector_db(api_key=api_key, embedding_model=embedding_model)
    table = db.open_table(TABLE_NAME)

    try:
        query_vector = get_embedding(query, api_key=api_key, embedding_model=embedding_model)
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
