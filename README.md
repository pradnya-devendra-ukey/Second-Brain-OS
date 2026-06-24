# 🧠 Second Brain OS

A local-first, RAG-powered personal knowledge management system. Upload PDFs, Markdown, and text files, take notes with bi-directional linking, and chat with your entire knowledge base using an AI copilot — powered by Google Gemini API.

---

## ✨ Features

- **📝 Note Editor** — rich text notes with auto-save and `[[wiki-link]]` support
- **📄 Document Ingestion** — upload PDF, `.md`, and `.txt` files; content is parsed and indexed automatically
- **🔍 Semantic Search (RAG)** — ask questions and get source-cited answers from your knowledge base
- **🕸️ Knowledge Graph** — interactive force-directed graph visualizing note connections
- **🗑️ Document Deletion** — delete files from SQLite, LanceDB vector database, and local uploads directory at once
- **🤖 Gemini AI Copilot** — streaming chat powered by `gemini-2.5-flash` and embeddings by `gemini-embedding-2`
- **🔑 Dynamic API Settings** — configure your Gemini API key and model globally via `.env` OR dynamically inside the browser settings modal (keys are securely sent via request headers)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Clone & set up the environment

```bash
git clone https://github.com/pradnya-devendra-ukey/second-brain-os.git
cd second-brain-os

python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (CMD):
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r backend/requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and paste your Gemini API key (optional - can also be configured in the UI)
```

Edit `.env`:
```env
GEMINI_API_KEY=AIzaSy...your-gemini-key...
```

### 3. Start the server

```bash
# Windows (double-click or run in terminal):
.\start.bat

# Or manually:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
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
│   │       └── vector_db.py        # LanceDB embed/search
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
| Embeddings | Google Gemini `gemini-embedding-2` |
| LLM | Google Gemini `gemini-2.5-flash` |
| Document Parsing | PyMuPDF (PDF), plain text for MD/TXT |
| Frontend | Vanilla HTML/CSS/JS (no framework) |

---

## ⚠️ Important Notes

- **`.env` is never committed** — it contains your API keys. Use `.env.example` as a template.
- **Dynamic Headers**: If you configure the API key in the UI settings, it is saved in browser local storage and sent in request headers (`X-Gemini-API-Key` and `X-Gemini-Model`) for dynamic configuration.
- The `uploads/`, `lancedb_data/`, and `*.db` files are excluded from git and are generated at runtime.
