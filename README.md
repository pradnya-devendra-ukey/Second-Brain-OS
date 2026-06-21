# 🧠 Second Brain OS

Second Brain OS is a premium, AI-powered personal knowledge assistant and semantic search engine. Built with a FastAPI backend and a beautiful glassmorphic frontend, it allows users to upload documents (PDFs, text notes, markdown files) and query them using modern Retrieval-Augmented Generation (RAG).

## 🚀 Features

- **Multi-Format Document Ingestion:** Supports PDF, TXT, and MD files.
- **Hybrid Embedding Pipeline:** Automatically indexes documents locally using HuggingFace (`all-MiniLM-L6-v2`) to save API costs.
- **RAG QA Chain:** Fully optimized retrieval chain using LangChain, supporting chat history and context synthesis.
- **Multi-LLM Integration:** Supports both Google Gemini (defaulting to `gemini-2.5-flash`) and OpenAI (`gpt-4o-mini`).
- **Modern UI:** Responsive sidebar control panel, real-time database status badges, and interactive chat interface.

---

## 🛠️ Local Setup

### 1. Prerequisites
- Python 3.10 or 3.11
- API Keys for Google Gemini or OpenAI

### 2. Installation
Clone the repository and install requirements inside a virtual environment:

```bash
# Clone the repository
git clone https://github.com/pradnya-devendra-ukey/Second-Brain-OS.git
cd Second-Brain-OS

# Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:

```env
GOOGLE_API_KEY="your_gemini_api_key"
OPENAI_API_KEY="your_openai_api_key"
```

### 4. Running the Application
Start the FastAPI server:

```bash
uvicorn main:app --reload
```
Open **http://127.0.0.1:8000** in your browser.

---

## 🐳 Docker Deployment

The application is fully containerized. You can build and run it with persistence:

```bash
# Build the Docker image
docker build -t second-brain-os .

# Run the container with volume mapping
docker run -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/vectordb:/app/vectordb \
  second-brain-os
```
