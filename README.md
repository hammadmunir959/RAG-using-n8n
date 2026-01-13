# Document Intelligence WebApp (Hybrid AI System)

A powerful, modern web application for intelligent document analysis. It utilizes a **Hybrid AI Architecture** that combines a high-performance local **LangGraph RAG** system as the primary engine, with a robust **n8n workflow** backing it up as a failover system.

Built with **React (Frontend)**, **FastAPI (Backend)**, **LangGraph (AI Agent)**, and **n8n (Workflow Automation)**.

## 🌟 Key Features

- **🧠 Hybrid AI Architecture**: 
  - **Primary**: Local LangGraph ReAct Agent (RAG) using Groq (Llama 3 70B) + ChromaDB.
  - **Fallback**: n8n Webhooks for redundancy and complex workflow orchestration.
- **📄 Universal Document Support**: Upload and analyze PDF, CSV, JSON, DOCX, and TXT files.
- **🔍 Intelligent RAG**: Automatically chunks, embeds, and indexes documents for context-aware Q&A.
- **🕷️ Self-Learning Crawler**: The Agent can "read" entire websites on demand to learn new information using an integrated Scrapy engine.
- **🌐 Web Search Capability**: The agent can search the web (via ScrapingAnt) if the answer isn't in your documents.
- **🎨 Modern UI**: Beautiful React interface with drag-and-drop upload, real-time chat, and markdown rendering.

## 🏗️ Architecture

```mermaid
graph LR
    User[User] --> Frontend[React Frontend]
    Frontend --> Backend[FastAPI Backend]
    Backend --> Router{AI Router}
    
    Router -- Primary Path --> LangGraph[LangGraph Agent]
    LangGraph --> Chroma[ChromaDB (Local Vector Store)]
    LangGraph --> Groq[Groq API (Llama 3)]
    
    LangGraph -- Tool Call --> CrawlerAPI[Crawler API]
    CrawlerAPI --> Scrapy[Scrapy Subprocess]
    Scrapy -- Ingest Data --> Chroma
    
    Router -- Fallback/Error --> N8N[n8n Workflows]
    N8N --> CloudAI[Cloud AI Services]
```

## 🚀 Quick Start

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.9+
- Node.js 18+

### 2. Configure Environment
Create a `.env` file in `backend/` based on `.env.example`:

```env
# LangGraph Configuration (Primary)
GROQ_API_KEY=your_groq_key_here
SCRAPER_ANT_API_KEY=your_scrapingant_key_here (optional, for web search)

# n8n Configuration (Fallback)
N8N_BASE_URL=http://localhost:5678
N8N_UPLOAD_WEBHOOK_ID=...
N8N_CHAT_WEBHOOK_ID=...
```

### 3. One-Command Start (Recommended)
We provide a unified startup script that checks dependencies, starts n8n (via Docker), and launches both frontend and backend.

```bash
chmod +x start.sh
./start.sh
```

- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8001
- **n8n**: http://localhost:5678

## 🛠️ Manual Setup

### Backend (Python/FastAPI)
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run server (Reload enabled)
uvicorn main:app --reload
```

### Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev
```

### n8n (Docker)
```bash
docker compose up -d
```
*Note: You must import `workflow.json` into n8n for the fallback system to work.*

## 📚 How It Works

### The "Dual-Engine" Approach
1. **Request**: User asks "What is the summary of the Q3 report?"
2. **Primary Engine (LangGraph)**:
   - The backend specifically checks if LangGraph is configured.
   - It retrieves relevant chunks from your local ChromaDB vector store.
   - It runs a ReAct agent using Groq's Llama 3 to formulate an answer.
   - **Benefit**: Extremely fast, private, and free (with Groq's free tier).
3. **Fallback Engine (n8n)**:
   - If Groq is down, or LangGraph errors out, the system **automatically** switches to n8n.
   - It sends the payload to your n8n webhook.
   - n8n executes its own RAG workflow.
   - **Benefit**: Robustness. The system never fails even if one part goes down.

### 🕷️ The "Sidecar" Crawler System
The system features a unique **Self-Learning** capability:
1. **Instruction**: You tell the agent "Crawl https://docs.example.com".
2. **Execution**: The Agent uses its `crawl_website` tool to trigger the Scrapy subsystem.
3. **Ingestion**: Scrapy runs as a safe, isolated background process. It crawls the site, extracts text, and **pushes it back** into the system's Vector Store (ChromaDB) via an internal API.
4. **Learning**: Once finished, the Agent can immediately answer questions about that website using its `retrieve_documents` tool, effectively "learning" the content on the fly.

## 🧩 API Endpoints

- `POST /api/upload`: Upload and index documents (PDF/CSV/TXT/JSON).
- `POST /api/chat`: Chat with the intelligent agent.
- `GET /api/documents`: List all indexed documents.
- `GET /api/system/status`: Check which AI engine is currently active.

## 📝 License
MIT License. Open source and free to use.
