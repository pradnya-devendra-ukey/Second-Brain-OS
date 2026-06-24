import json
from typing import Generator, List, Dict, Any
from google import genai
from google.genai import types
from app.config import settings
from app.services.vector_db import search_vector_db

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

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """Splits a document text into smaller overlapping chunks recursively."""
    if not text:
        return []
        
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
            
        # If adding paragraph exceeds chunk_size
        if len(current_chunk) + len(paragraph) + 2 > chunk_size:
            # If current_chunk has content, push it
            if current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - chunk_overlap)
                # Find space to avoid splitting words
                space_idx = current_chunk.find(" ", overlap_start)
                if space_idx != -1:
                    current_chunk = current_chunk[space_idx:]
                else:
                    current_chunk = current_chunk[-chunk_overlap:]
            
            # If paragraph itself is larger than chunk_size, split by sentences
            if len(paragraph) > chunk_size:
                sentences = paragraph.replace(". ", ".\n").split("\n")
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    if len(current_chunk) + len(sentence) + 1 > chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            overlap_start = max(0, len(current_chunk) - chunk_overlap)
                            space_idx = current_chunk.find(" ", overlap_start)
                            current_chunk = current_chunk[space_idx:] if space_idx != -1 else current_chunk[-chunk_overlap:]
                        
                        # If sentence itself is still too long, split by characters/words
                        if len(sentence) > chunk_size:
                            words = sentence.split(" ")
                            for word in words:
                                if len(current_chunk) + len(word) + 1 > chunk_size:
                                    chunks.append(current_chunk.strip())
                                    current_chunk = word
                                else:
                                    current_chunk += " " + word if current_chunk else word
                        else:
                            current_chunk += " " + sentence if current_chunk else sentence
                    else:
                        current_chunk += " " + sentence if current_chunk else sentence
            else:
                current_chunk += "\n\n" + paragraph if current_chunk else paragraph
        else:
            current_chunk += "\n\n" + paragraph if current_chunk else paragraph
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

def build_rag_prompt(query: str, context_chunks: List[Dict[str, Any]], history: List[Dict[str, str]] = None) -> tuple:
    """Builds a system instruction and chat history for Gemini.
    
    Returns (system_instruction, contents) where contents is a list of
    Content objects for the Gemini API.
    """
    system_instruction = (
        "You are the AI Companion for the Second Brain OS.\n"
        "You help the user explore and synthesize their notes, documents, and personal knowledge base.\n\n"
        "Here are the core rules:\n"
        "1. Answer the user's question using the retrieved Context chunks below. Make sure to cite the files/notes from which you got information.\n"
        "2. If the context does not contain enough information to answer, state this honestly. You may use your general knowledge, but clearly state what came from the context vs. what is external.\n"
        "3. Provide clear, professional, markdown-formatted responses. Use bullet points and code blocks where helpful.\n"
        "4. DO NOT make up facts. Be precise.\n\n"
        "--- START CONTEXT CHUNKS ---\n"
    )
    
    # Add context chunks
    for i, chunk in enumerate(context_chunks):
        title = chunk.get("doc_title", "Untitled Document")
        text = chunk.get("text", "")
        system_instruction += f"Chunk [{i+1}] - File/Note: '{title}':\n{text}\n\n"
        
    system_instruction += "--- END CONTEXT CHUNKS ---"
    
    # Build chat history as Gemini Content objects
    contents = []
    if history:
        for msg in history:
            contents.append(
                types.Content(
                    role="user" if msg["role"] == "user" else "model",
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )
    
    # Add the current user query
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)]
        )
    )
    
    return system_instruction, contents

def run_rag_stream(
    query: str,
    history: List[Dict[str, str]] = None,
    top_k: int = 5,
    api_key: str = None,
    llm_model: str = None,
    embedding_model: str = None
) -> Generator[str, None, None]:
    """Executes vector search and streams the response from Gemini."""
    # 1. Search vector DB
    chunks = search_vector_db(query, top_k=top_k, api_key=api_key, embedding_model=embedding_model)
    
    # Send the retrieved sources first so the frontend knows what is referenced
    sources = []
    for c in chunks:
        sources.append({
            "doc_id": c["doc_id"],
            "title": c["doc_title"],
            "text": c["text"][:200] + "..." # Snippet
        })
        
    # We yield the sources as a structured JSON prefix so the frontend can extract it.
    # Format: [SOURCES]json_data[SOURCES]
    yield f"[SOURCES]{json.dumps(sources)}[SOURCES]"
    
    # 2. Build system instruction and contents
    system_instruction, contents = build_rag_prompt(query, chunks, history)
    
    # 3. Call Gemini with streaming enabled
    try:
        client = get_client(api_key)
    except ValueError as e:
        yield f"\n\n*Error: {str(e)}*"
        return
        
    active_llm_model = llm_model or settings.LLM_MODEL
    try:
        response = client.models.generate_content_stream(
            model=active_llm_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=4096,
            ),
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        yield f"\n\n*Error generating response from Gemini: {str(e)}*"
