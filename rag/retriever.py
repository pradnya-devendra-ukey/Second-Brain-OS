import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_chroma import Chroma
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Load environment variables
load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "vectordb"

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

    google_api_key = os.environ.get("GOOGLE_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if google_api_key:
        return "google"
    elif openai_api_key:
        return "openai"
    return "local"

def get_embeddings(provider: str = None):
    """Retrieve embedding model based on provider or available environment variables."""
    if provider is None:
        provider = get_embeddings_provider()

    if provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
    elif provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")
    elif provider == "local":
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")

def get_vectorstore():
    """Load the existing vector store from the database directory."""
    if not DB_DIR.exists():
        raise FileNotFoundError(f"Vector database directory not found at {DB_DIR}. Please run ingestion first.")
    
    # Read saved embedding provider from metadata to initialize the correct embeddings function
    saved_provider = "local"
    meta_path = DB_DIR / "meta.json"
    if meta_path.exists():
        import json
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            saved_provider = meta.get("embedding_provider", "local")
        except Exception as e:
            print(f"Warning: Could not read DB metadata: {e}")

    embeddings = get_embeddings(provider=saved_provider)
    return Chroma(
        persist_directory=str(DB_DIR),
        embedding_function=embeddings
    )

def get_retriever(search_type="similarity", search_kwargs=None):
    """Get retriever from vector store."""
    if search_kwargs is None:
        search_kwargs = {"k": 4}
    
    vectorstore = get_vectorstore()
    return vectorstore.as_retriever(search_type=search_type, search_kwargs=search_kwargs)

def get_llm():
    """Retrieve chat model based on available environment variables."""
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    openai_api_key = os.environ.get("OPENAI_API_KEY")

    if google_api_key:
        print("Using ChatGoogleGenerativeAI (gemini-2.5-flash)...")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    elif openai_api_key:
        print("Using ChatOpenAI (gpt-4o-mini)...")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    else:
        raise ValueError("Neither GOOGLE_API_KEY nor OPENAI_API_KEY found. Check your .env file.")

def get_qa_chain():
    """Build and return a combined retrieval QA chain with history support."""
    llm = get_llm()
    retriever = get_retriever()

    # 1. Create history-aware retriever
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, "
        "just reformulate it if needed and otherwise return it as is."
    )
    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    # 2. Create the QA chain
    system_prompt = (
        "You are an assistant for question-answering tasks. "
        "Use the following pieces of retrieved context to answer the question. "
        "If you don't know the answer, say that you don't know. "
        "Keep the answer concise and professional.\n\n"
        "Context:\n{context}"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    return rag_chain

if __name__ == "__main__":
    # Test connection
    try:
        store = get_vectorstore()
        print("Successfully connected to Chroma Vector Store!")
        print(f"Embedding function: {store.embeddings.__class__.__name__}")
    except Exception as e:
        print(f"Could not connect to Vector DB: {e}")

