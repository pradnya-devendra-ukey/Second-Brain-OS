import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFDirectoryLoader, DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

# Load environment variables
load_dotenv(override=True)

# Define paths 
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
NOTES_DIR = DATA_DIR / "notes"
DB_DIR = BASE_DIR / "vectordb"

def get_embeddings(provider: str = None):
    """Retrieve embedding model based on provider or available environment variables."""
    if provider is None:
        provider = get_embeddings_provider()

    if provider == "google":
        print("Using Google Generative AI Embeddings...")
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
    elif provider == "openai":
        print("Using OpenAI Embeddings...")
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")
    elif provider == "local":
        print("Using Local HuggingFace Embeddings (all-MiniLM-L6-v2)...")
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    else:
        print(f"Error: Unknown embedding provider '{provider}'.")
        sys.exit(1)

def clear_vector_db(embeddings=None):
    """Clear the vector database by deleting the collection or clearing files."""
    if embeddings is not None:
        try:
            print("Clearing vector database collection programmatically...")
            from langchain_chroma import Chroma
            vectorstore = Chroma(
                persist_directory=str(DB_DIR),
                embedding_function=embeddings
            )
            vectorstore.delete_collection()
            print("Collection cleared successfully!")
            return
        except Exception as e:
            print(f"Failed to delete collection programmatically: {e}. Falling back to file deletion...")

    import shutil
    if DB_DIR.exists():
        print(f"Clearing vector database files at {DB_DIR}...")
        for path in DB_DIR.iterdir():
            if path.name != ".gitkeep":
                try:
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        shutil.rmtree(path)
                except Exception as e:
                    print(f"Error clearing vector DB path {path}: {e}")

def get_embeddings_provider():
    """Determine embedding provider based on metadata or environment variables."""
    meta_path = DB_DIR / "meta.json"
    if meta_path.exists():
        try:
            import json
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            provider = meta.get("embedding_provider")
            if provider:
                return provider
        except Exception:
            pass

    google_api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if google_api_key:
        return "google"
    elif openai_api_key:
        return "openai"
    return "local"

def save_metadata(provider: str):
    """Save vector database metadata (embedding model provider)."""
    import json
    DB_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = DB_DIR / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"embedding_provider": provider}, f)
    print(f"Saved DB metadata: {provider}")

def ingest_documents(clear_db: bool = False, embedding_provider: str = None) -> int:
    """Load, split, and ingest documents into the Chroma vector database.
    
    Returns:
        int: Number of chunks successfully ingested.
    """
    # Ensure directories exist
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    DB_DIR.mkdir(parents=True, exist_ok=True)

    if embedding_provider is None:
        embedding_provider = get_embeddings_provider()
    embeddings = get_embeddings(provider=embedding_provider)

    if clear_db:
        clear_vector_db(embeddings=embeddings)

    documents = []

    # 1. Load PDFs
    print(f"Loading PDFs from {PDF_DIR}...")
    pdf_loader = PyPDFDirectoryLoader(str(PDF_DIR))
    pdf_docs = pdf_loader.load()
    print(f"Loaded {len(pdf_docs)} PDF pages/documents.")
    documents.extend(pdf_docs)

    # 2. Load Notes (Text/Markdown files)
    print(f"Loading notes from {NOTES_DIR}...")
    # DirectoryLoader can load all text files recursively
    notes_loader = DirectoryLoader(
        str(NOTES_DIR),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}
    )
    md_loader = DirectoryLoader(
        str(NOTES_DIR),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}
    )

    try:
        notes_docs = notes_loader.load()
        print(f"Loaded {len(notes_docs)} text note documents.")
        documents.extend(notes_docs)
    except Exception as e:
        print(f"No notes loaded (or folder is empty): {e}")

    try:
        md_docs = md_loader.load()
        print(f"Loaded {len(md_docs)} markdown note documents.")
        documents.extend(md_docs)
    except Exception as e:
        print(f"No markdown notes loaded (or folder is empty): {e}")

    if not documents:
        print("No documents found to ingest. Please place files in data/pdfs/ or data/notes/.")
        return 0

    # 3. Split documents
    print("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,
        chunk_overlap=300,
        add_start_index=True
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Created {len(chunks)} text chunks.")

    # 4. Initialize Vector Store and add documents
    provider = embedding_provider
    
    print(f"Connecting to Vector DB at {DB_DIR}...")
    
    vectorstore = Chroma(
        persist_directory=str(DB_DIR),
        embedding_function=embeddings
    )
    
    # Ingest in batches to avoid API rate limits/quotas
    batch_size = 50
    import time
    
    print(f"Indexing {len(chunks)} chunks in batches of {batch_size}...")
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        print(f"Indexing batch {i // batch_size + 1}/{-(-len(chunks) // batch_size)} (chunks {i} to {i + len(batch)})...")
        
        max_retries = 5
        retry_delay = 5.0
        success = False
        
        for attempt in range(max_retries):
            try:
                vectorstore.add_documents(batch)
                success = True
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2 ** attempt)
                    print(f"  Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                else:
                    print("  Failed to index batch after maximum retries.")
                    raise e
        
        if i + batch_size < len(chunks):
            time.sleep(2.0)

    
    if provider:
        save_metadata(provider)
        
    print("Ingestion complete! Vector database successfully updated.")
    return len(chunks)

if __name__ == "__main__":
    ingest_documents()

