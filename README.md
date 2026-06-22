# 🧠 Second Brain OS

A local-first, RAG-powered personal knowledge management system. Upload PDFs, Markdown, and text files, take notes with bi-directional linking, and chat with your entire knowledge base using an AI copilot — all running on your own machine with Ollama or OpenAI.

---

## ✨ Features

- **📝 Note Editor** — rich text notes with auto-save and `[[wiki-link]]` support
- **📄 Document Ingestion** — upload PDF, `.md`, and `.txt` files; content is parsed and indexed automatically
- **🔍 Semantic Search (RAG)** — ask questions and get source-cited answers from your knowledge base
- **🕸️ Knowledge Graph** — interactive force-directed graph visualizing note connections
- **🤖 AI Copilot** — streaming chat powered by OpenAI GPT or local Ollama (fully offline)
- **🔄 Auto Dimension Handling** — switching between OpenAI ↔ Ollama embeddings automatically recreates the vector store

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) (for local/offline mode) **or** an OpenAI API key (for cloud mode)

### 1. Clone & set up the environment

```bash
git clone https://github.com/pradnya-devendra-ukey/second-brain-os.git
cd second-brain-os

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your preferred settings
```

**For local/offline mode (Ollama):**
```env
USE_LOCAL_LLM=True
OLLAMA_LLM_MODEL=llama3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```
Pull required models first:
```bash
ollama pull llama3
ollama pull nomic-embed-text
```

**For cloud mode (OpenAI):**
```env
USE_LOCAL_LLM=False
OPENAI_API_KEY=sk-...your-key...
```

### 3. Start the server

```bash
# Windows (double-click or run in terminal):
start.bat

# Or manually:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

Open **http://localhost:8000** in your browser.

---

## 🗂️ Project Structure

```
second-brain-os/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (pydantic-settings + .env)
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── database/
│   │   │   ├── db.py            # SQLAlchemy engine & session
│   │   │   └── models.py        # Note, ChatSession, ChatMessage models
│   │   ├── routers/
│   │   │   ├── notes.py         # CRUD + wiki-link parser
│   │   │   ├── documents.py     # File upload & ingestion endpoint
│   │   │   └── chat.py          # RAG chat + streaming endpoint
│   │   └── services/
│   │       ├── document_parser.py  # PDF / MD / TXT extraction
│   │       ├── rag_service.py      # Chunking + LLM streaming
│   │       └── vector_db.py        # LanceDB embed/search (auto-dim fix)
│   ├── static/
│   │   ├── index.html           # Single-page frontend
│   │   ├── index.css            # Styles
│   │   └── index.js             # All frontend logic
│   └── requirements.txt
├── .env.example                 # Environment variable template
├── requirements.txt
└── start.bat                    # Windows one-click launcher
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Database | SQLite (SQLAlchemy) |
| Vector Store | LanceDB |
| Embeddings | OpenAI `text-embedding-3-small` or Ollama `nomic-embed-text` |
| LLM | OpenAI GPT-4o-mini or Ollama `llama3` |
| Document Parsing | PyMuPDF (PDF), plain text for MD/TXT |
| Frontend | Vanilla HTML/CSS/JS (no framework) |

---

## ⚠️ Important Notes

- **`.env` is never committed** — it contains your API keys. Use `.env.example` as a template.
- **Switching embedding providers** (OpenAI ↔ Ollama) will automatically drop and recreate the LanceDB vector table (different dimensions). Previously indexed documents will need to be re-uploaded.
- The `uploads/`, `lancedb_data/`, and `*.db` files are excluded from git and are generated at runtime.
