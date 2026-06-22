import json
from typing import Generator, List, Dict, Any
from openai import OpenAI
import httpx
from app.config import settings
from app.services.vector_db import search_vector_db

openai_client = None
if settings.OPENAI_API_KEY:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

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

def build_rag_prompt(query: str, context_chunks: List[Dict[str, Any]], history: List[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """Builds a chat message history including relevant knowledge context and prompt guidelines."""
    system_prompt = (
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
        system_prompt += f"Chunk [{i+1}] - File/Note: '{title}':\n{text}\n\n"
        
    system_prompt += "--- END CONTEXT CHUNKS ---"
    
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add chat history if available
    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
    # Add the current user query
    messages.append({"role": "user", "content": query})
    
    return messages

def run_rag_stream(query: str, history: List[Dict[str, str]] = None, top_k: int = 5) -> Generator[str, None, None]:
    """Executes vector search and streams the response from LLM (OpenAI or Ollama)."""
    # 1. Search vector DB
    chunks = search_vector_db(query, top_k=top_k)
    
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
    
    # 2. Build messages list
    messages = build_rag_prompt(query, chunks, history)
    
    # 3. Call LLM with streaming enabled
    if settings.USE_LOCAL_LLM:
        try:
            # Query Ollama streaming
            with httpx.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_LLM_MODEL,
                    "messages": messages,
                    "stream": True
                },
                timeout=60.0
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk_data = json.loads(line)
                        if "message" in chunk_data and "content" in chunk_data["message"]:
                            yield chunk_data["message"]["content"]
        except Exception as e:
            yield f"\n\n*Error generating response from local LLM (Ollama): {str(e)}*"
    else:
        if not settings.OPENAI_API_KEY:
            yield "\n\n*Error: OpenAI API Key is missing. Please set it in your .env or configure local LLM.*"
            return
            
        try:
            stream = openai_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"\n\n*Error generating response from OpenAI: {str(e)}*"
