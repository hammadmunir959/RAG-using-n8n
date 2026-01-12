from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx
from dotenv import load_dotenv
load_dotenv()  # Load .env file before other imports
import os
import asyncio
from pathlib import Path
from typing import Optional, List, Tuple
from pydantic import BaseModel
import logging
import json
from sqlalchemy.orm import Session
from database import (
    init_db, get_db, cleanup_db, create_document, get_document, get_documents, delete_document,
    create_conversation, get_conversation, get_conversations, delete_conversation,
    update_conversation_title, create_message, get_messages,
    update_document_summary, get_documents_pending_summary, SessionLocal
)

# LangGraph Fallback Imports
from vector_store import init_vector_store, get_vector_store
from langgraph_agent import run_agent, is_langgraph_available, get_langgraph_status


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Intelligence API")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    # Initialize vector store for LangGraph fallback
    try:
        init_vector_store()
        logger.info("Vector store initialized")
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
    
    logger.info("Database initialized")


# Cleanup database connections on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    cleanup_db()
    logger.info("Application shutdown - database connections closed")


@app.get("/api/system/status")
async def get_system_status():
    """Get system status including LangGraph (primary) and n8n (fallback) availability."""
    langgraph_status = get_langgraph_status()
    return {
        "status": "online",
        "architecture": {
            "primary": "LangGraph",
            "fallback": "n8n"
        },
        "langgraph": langgraph_status,
        "langgraph_is_primary": True,
        "n8n_url": N8N_BASE_URL,
        "n8n_is_fallback": True
    }


# Available Groq models with metadata
GROQ_MODELS = [
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "provider": "Meta", "speed": 280, "input_price": 0.59, "output_price": 0.79, "context": 131072, "free": False, "type": "production"},
    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant", "provider": "Meta", "speed": 560, "input_price": 0.05, "output_price": 0.08, "context": 131072, "free": False, "type": "production"},
    {"id": "openai/gpt-oss-120b", "name": "GPT OSS 120B", "provider": "OpenAI", "speed": 500, "input_price": 0.15, "output_price": 0.60, "context": 131072, "free": False, "type": "production"},
    {"id": "openai/gpt-oss-20b", "name": "GPT OSS 20B", "provider": "OpenAI", "speed": 1000, "input_price": 0.075, "output_price": 0.30, "context": 131072, "free": False, "type": "production"},
    {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "name": "Llama 4 Maverick 17B", "provider": "Meta", "speed": 600, "input_price": 0.20, "output_price": 0.60, "context": 131072, "free": False, "type": "preview"},
    {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "name": "Llama 4 Scout 17B", "provider": "Meta", "speed": 750, "input_price": 0.11, "output_price": 0.34, "context": 131072, "free": False, "type": "preview"},
    {"id": "qwen/qwen3-32b", "name": "Qwen 3 32B", "provider": "Alibaba", "speed": 400, "input_price": 0.29, "output_price": 0.59, "context": 131072, "free": False, "type": "preview"},
    {"id": "moonshotai/kimi-k2-instruct-0905", "name": "Kimi K2", "provider": "Moonshot AI", "speed": 200, "input_price": 1.00, "output_price": 3.00, "context": 262144, "free": False, "type": "preview"},
]


class SettingsUpdate(BaseModel):
    groq_api_key: Optional[str] = None
    scraper_ant_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    n8n_base_url: Optional[str] = None
    n8n_upload_webhook_id: Optional[str] = None
    n8n_chat_webhook_path: Optional[str] = None


@app.get("/api/settings")
async def get_settings():
    """Get current settings (API keys are masked)."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    scraper_key = os.getenv("SCRAPER_ANT_API_KEY", "")
    
    return {
        "groq_api_key": f"{'*' * 20}{groq_key[-8:]}" if len(groq_key) > 8 else ("*" * len(groq_key) if groq_key else ""),
        "groq_api_key_set": bool(groq_key),
        "scraper_ant_api_key": f"{'*' * 16}{scraper_key[-6:]}" if len(scraper_key) > 6 else ("*" * len(scraper_key) if scraper_key else ""),
        "scraper_ant_api_key_set": bool(scraper_key),
        "llm_model": os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        "n8n_base_url": os.getenv("N8N_BASE_URL", "http://localhost:5678"),
        "n8n_upload_webhook_id": os.getenv("N8N_UPLOAD_WEBHOOK_ID", ""),
        "n8n_chat_webhook_path": os.getenv("N8N_CHAT_WEBHOOK_PATH", ""),
        "available_models": GROQ_MODELS
    }


@app.put("/api/settings")
async def update_settings(settings: SettingsUpdate):
    """Update settings by modifying .env file."""
    try:
        env_path = Path(__file__).parent / ".env"
        
        # Read current .env file
        if env_path.exists():
            with open(env_path, "r") as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Create a dict of current values
        env_dict = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_dict[key.strip()] = value.strip()
        
        # Update with new values
        updates = {}
        if settings.groq_api_key and not settings.groq_api_key.startswith("*"):
            updates["GROQ_API_KEY"] = settings.groq_api_key
        if settings.scraper_ant_api_key and not settings.scraper_ant_api_key.startswith("*"):
            updates["SCRAPER_ANT_API_KEY"] = settings.scraper_ant_api_key
        if settings.llm_model:
            updates["LLM_MODEL"] = settings.llm_model
        if settings.n8n_base_url:
            updates["N8N_BASE_URL"] = settings.n8n_base_url
        if settings.n8n_upload_webhook_id:
            updates["N8N_UPLOAD_WEBHOOK_ID"] = settings.n8n_upload_webhook_id
        if settings.n8n_chat_webhook_path:
            updates["N8N_CHAT_WEBHOOK_PATH"] = settings.n8n_chat_webhook_path
        
        env_dict.update(updates)
        
        # Write back to .env
        with open(env_path, "w") as f:
            f.write("# LangGraph Configuration (Primary)\n")
            f.write(f"GROQ_API_KEY={env_dict.get('GROQ_API_KEY', '')}\n")
            f.write(f"SCRAPER_ANT_API_KEY={env_dict.get('SCRAPER_ANT_API_KEY', '')}\n")
            f.write("\n# n8n Configuration (Fallback)\n")
            f.write(f"N8N_BASE_URL={env_dict.get('N8N_BASE_URL', 'http://localhost:5678')}\n")
            f.write(f"N8N_UPLOAD_WEBHOOK_ID={env_dict.get('N8N_UPLOAD_WEBHOOK_ID', '')}\n")
            f.write(f"N8N_CHAT_WEBHOOK_ID={env_dict.get('N8N_CHAT_WEBHOOK_ID', '')}\n")
            f.write(f"N8N_CHAT_WEBHOOK_PATH={env_dict.get('N8N_CHAT_WEBHOOK_PATH', '')}\n")
            f.write(f"N8N_BASIC_AUTH_USER={env_dict.get('N8N_BASIC_AUTH_USER', '')}\n")
            f.write(f"N8N_BASIC_AUTH_PASSWORD={env_dict.get('N8N_BASIC_AUTH_PASSWORD', '')}\n")
            f.write(f"N8N_SUMMARY_WEBHOOK_ID={env_dict.get('N8N_SUMMARY_WEBHOOK_ID', '')}\n")
            f.write("\n# Model Settings\n")
            f.write(f"LLM_MODEL={env_dict.get('LLM_MODEL', 'llama-3.3-70b-versatile')}\n")
            f.write(f"EMBEDDING_MODEL={env_dict.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}\n")
            f.write("\n# Database\n")
            f.write(f"DATABASE_URL={env_dict.get('DATABASE_URL', 'sqlite:///./data/app.db')}\n")
        
        # Update environment variables in current process
        for key, value in updates.items():
            os.environ[key] = value
        
        logger.info(f"Settings updated: {list(updates.keys())}")
        
        return {
            "success": True,
            "message": "Settings updated successfully. Some changes may require server restart.",
            "updated_keys": list(updates.keys())
        }
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")

# CORS configuration - must be added before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:8000"],  # React dev servers and production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
) 

# Environment variables
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
N8N_UPLOAD_WEBHOOK_ID = os.getenv("N8N_UPLOAD_WEBHOOK_ID", "d5f0f619-e0b4-4e7b-a9f4-d5b84d978651")
N8N_CHAT_WEBHOOK_ID = os.getenv("N8N_CHAT_WEBHOOK_ID", "66219e80-fbed-4664-a11d-4a05167fbad2")
N8N_SUMMARY_WEBHOOK_ID = os.getenv("N8N_SUMMARY_WEBHOOK_ID", "")  # Optional: webhook for summary generation
# Allow overriding the full chat webhook path (for nodes that don't expose an ID)
N8N_CHAT_WEBHOOK_PATH = os.getenv(
    "N8N_CHAT_WEBHOOK_PATH",
    f"{N8N_CHAT_WEBHOOK_ID}/chat" if N8N_CHAT_WEBHOOK_ID else "chat"
)
N8N_BASIC_AUTH_USER = os.getenv("N8N_BASIC_AUTH_USER", "admin")
N8N_BASIC_AUTH_PASSWORD = os.getenv("N8N_BASIC_AUTH_PASSWORD", "admin")


# Request models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None

class ConversationTitleUpdate(BaseModel):
    title: str

# Get the path to the frontend dist directory
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

# Mount static files for assets (CSS, JS, images, etc.)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

@app.get("/")
async def root():
    """Serve the frontend index.html"""
    if FRONTEND_DIST.exists():
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
    return {"message": "Document Intelligence API is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/test-n8n")
async def test_n8n_connection():
    """
    Test endpoint to verify FastAPI → n8n connection (First Principles Testing)
    This confirms webhook URLs are correct before connecting React.
    """
    results = {
        "upload_webhook": {"url": f"{N8N_BASE_URL}/webhook/{N8N_UPLOAD_WEBHOOK_ID}", "status": None, "message": ""},
        "chat_webhook": {"url": f"{N8N_BASE_URL}/webhook/{N8N_CHAT_WEBHOOK_PATH}", "status": None, "message": ""}
    }
    
    auth = None
    if N8N_BASIC_AUTH_USER and N8N_BASIC_AUTH_PASSWORD:
        auth = (N8N_BASIC_AUTH_USER, N8N_BASIC_AUTH_PASSWORD)
    
    # Test Upload Webhook
    try:
        test_content = b'{"test": "data"}'
        files = {"Upload_Document": ("test.json", test_content, "application/json")}
        async with httpx.AsyncClient(timeout=10.0) as client:
            if auth:
                response = await client.post(results["upload_webhook"]["url"], files=files, auth=auth)
            else:
                response = await client.post(results["upload_webhook"]["url"], files=files)
        
        results["upload_webhook"]["status"] = response.status_code
        results["upload_webhook"]["message"] = "✅ Working" if response.status_code == 200 else f"❌ Failed: {response.text[:100]}"
    except Exception as e:
        results["upload_webhook"]["status"] = "error"
        results["upload_webhook"]["message"] = f"❌ Error: {str(e)}"
    
    # Test Chat Webhook
    try:
        payload = {"chatInput": "Test from FastAPI", "message": "Test from FastAPI"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            if auth:
                response = await client.post(results["chat_webhook"]["url"], json=payload, auth=auth)
            else:
                response = await client.post(results["chat_webhook"]["url"], json=payload)
        
        results["chat_webhook"]["status"] = response.status_code
        if response.status_code == 200:
            results["chat_webhook"]["message"] = "✅ Working"
        elif response.status_code == 404:
            results["chat_webhook"]["message"] = f"❌ Webhook not found. Update N8N_CHAT_WEBHOOK_ID in backend/main.py"
        else:
            results["chat_webhook"]["message"] = f"❌ Failed: {response.text[:100]}"
    except Exception as e:
        results["chat_webhook"]["status"] = "error"
        results["chat_webhook"]["message"] = f"❌ Error: {str(e)}"
    
    return {
        "architecture": "React → FastAPI → n8n (correct flow to avoid CORS)",
        "n8n_base_url": N8N_BASE_URL,
        "test_results": results,
        "instructions": {
            "if_chat_fails": "1. Go to http://localhost:5678\n2. Open your chat workflow\n3. Click the Chat Trigger node\n4. Copy the Production URL webhook ID (not test URL)\n5. Update N8N_CHAT_WEBHOOK_ID in backend/main.py or set as environment variable"
        }
    }

# Explicit OPTIONS handlers for CORS preflight
@app.options("/api/upload")
async def options_upload():
    return JSONResponse(status_code=200, content={})

@app.options("/api/chat")
async def options_chat():
    return JSONResponse(status_code=200, content={})

@app.options("/api/documents")
async def options_documents():
    return JSONResponse(status_code=200, content={})

@app.options("/api/conversations")
async def options_conversations():
    return JSONResponse(status_code=200, content={})

# Document Management Endpoints

@app.get("/api/documents")
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List all uploaded documents with metadata and summaries."""
    try:
        documents = get_documents(db, skip=skip, limit=limit)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "documents": [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "file_type": doc.file_type,
                        "upload_date": doc.upload_date.isoformat(),
                        "file_size": doc.file_size,
                        "status": doc.status,
                        "metadata": doc.meta_data,
                        "summary": doc.summary,
                        "summary_status": doc.summary_status or "pending",
                        "summary_error": doc.summary_error
                    }
                    for doc in documents
                ],
                "total": len(documents)
            }
        )
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/api/documents/{document_id}")
async def delete_document_endpoint(document_id: int, db: Session = Depends(get_db)):
    """Delete a document by ID."""
    try:
        success = delete_document(db, document_id)
        if success:
            # Remove from vector store
            try:
                vs = get_vector_store()
                vs.delete_document(document_id)
                logger.info(f"Deleted document {document_id} from vector store")
            except Exception as e:
                logger.error(f"Failed to delete document {document_id} from vector store: {e}")

            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"Document {document_id} deleted successfully"}
            )
        else:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Conversation Management Endpoints

@app.get("/api/conversations")
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List all conversations."""
    try:
        conversations = get_conversations(db, skip=skip, limit=limit)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "conversations": [
                    {
                        "id": conv.id,
                        "title": conv.title,
                        "created_at": conv.created_at.isoformat(),
                        "updated_at": conv.updated_at.isoformat(),
                        "message_count": len(conv.messages)
                    }
                    for conv in conversations
                ],
                "total": len(conversations)
            }
        )
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/conversations/{conversation_id}")
async def get_conversation_endpoint(conversation_id: int, db: Session = Depends(get_db)):
    """Get a conversation with all its messages."""
    try:
        conv = get_conversation(db, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "conversation": {
                    "id": conv.id,
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "messages": [
                        {
                            "id": msg.id,
                            "role": msg.role,
                            "content": msg.content,
                            "created_at": msg.created_at.isoformat(),
                            "sources": msg.sources
                        }
                        for msg in conv.messages
                    ]
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: int, db: Session = Depends(get_db)):
    """Delete a conversation by ID."""
    try:
        success = delete_conversation(db, conversation_id)
        if success:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"Conversation {conversation_id} deleted successfully"}
            )
        else:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.patch("/api/conversations/{conversation_id}/title")
async def update_conversation_title_endpoint(
    conversation_id: int,
    title_update: ConversationTitleUpdate,
    db: Session = Depends(get_db)
):
    """Update conversation title."""
    try:
        conv = update_conversation_title(db, conversation_id, title_update.title)
        if conv:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "conversation": {
                        "id": conv.id,
                        "title": conv.title,
                        "updated_at": conv.updated_at.isoformat()
                    }
                }
            )
        else:
            raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation title: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def validate_file_type(filename: str, content_type: str) -> Tuple[str, str]:
    """Validate file type and return file_type and normalized content_type."""
    allowed_types = [
        "application/pdf", "text/csv", "application/json", "text/plain",
        "application/vnd.ms-excel",  # Excel CSV
        "text/comma-separated-values",  # Alternative CSV MIME type
        "application/octet-stream"  # Allow octet-stream if extension matches
    ]
    
    file_ext = os.path.splitext(filename)[1].lower() if filename else ""
    allowed_extensions = [".pdf", ".csv", ".json", ".txt"]
    
    # Map extensions to file types
    ext_to_type = {
        ".pdf": "pdf",
        ".csv": "csv",
        ".json": "json",
        ".txt": "txt"
    }
    
    # If content type is octet-stream, rely on extension
    if content_type == "application/octet-stream":
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type {content_type} not allowed. Allowed types: PDF, CSV, JSON, TXT"
            )
        file_type = ext_to_type.get(file_ext, "unknown")
        return file_type, content_type
    
    if content_type not in allowed_types and file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {content_type} not allowed. Allowed types: PDF, CSV, JSON, TXT"
        )
    
    # Determine file type from extension or content type
    if file_ext in ext_to_type:
        file_type = ext_to_type[file_ext]
    elif "pdf" in content_type.lower():
        file_type = "pdf"
    elif "csv" in content_type.lower():
        file_type = "csv"
    elif "json" in content_type.lower():
        file_type = "json"
    elif "text" in content_type.lower():
        file_type = "txt"
    else:
        file_type = "unknown"
    
    return file_type, content_type

async def upload_single_file(file: UploadFile, db: Session, background_tasks: BackgroundTasks) -> dict:
    """Upload a single file and return document info."""
    logger.info(f"Processing file: {file.filename}, type: {file.content_type}")
    
    # Validate file type
    file_type, normalized_content_type = validate_file_type(file.filename, file.content_type or "application/octet-stream")
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    logger.info(f"File read successfully, size: {file_size} bytes")
    
    # Create document record in database
    doc = create_document(
        db=db,
        filename=file.filename,
        file_type=file_type,
        file_size=file_size,
        status="processing",
        metadata={"content_type": normalized_content_type}
    )
    
    # Background Task: Index document for LangGraph fallback
    try:
        async def background_index_document(doc_id: int, filename: str, content: bytes):
            try:
                vs = get_vector_store()
                await vs.add_document(doc_id, filename, content)
                logger.info(f"Background indexing completed for document {doc_id}")
            except Exception as e:
                logger.error(f"Background indexing failed for document {doc_id}: {e}")
        
        # Add to background tasks
        background_tasks.add_task(background_index_document, doc.id, file.filename, file_content)
    except Exception as e:
        logger.error(f"Failed to schedule background indexing: {e}")
    
    # Prepare form data for n8n webhook
    files = {
        "Upload_Document": (file.filename, file_content, normalized_content_type)
    }
    
    # Forward to n8n form webhook
    webhook_url = f"{N8N_BASE_URL}/form/{N8N_UPLOAD_WEBHOOK_ID}"
    logger.info(f"Forwarding to n8n webhook: {webhook_url}")
    
    # Prepare auth if basic auth is enabled
    auth = None
    if N8N_BASIC_AUTH_USER and N8N_BASIC_AUTH_PASSWORD:
        auth = (N8N_BASIC_AUTH_USER, N8N_BASIC_AUTH_PASSWORD)
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if auth:
                response = await client.post(webhook_url, files=files, auth=auth)
            else:
                response = await client.post(webhook_url, files=files)
            
            logger.info(f"n8n webhook response status: {response.status_code}")
            
            if response.status_code == 200:
                # Update document status to processed
                doc.status = "processed"
                db.commit()
                
                # Trigger summary generation in background
                background_tasks.add_task(generate_summary_for_document, doc.id)
                
                logger.info(f"Document {file.filename} uploaded successfully")
                return {
                    "success": True,
                    "message": f"Document '{file.filename}' uploaded and processed successfully",
                    "filename": file.filename,
                    "document_id": doc.id
                }
            else:
                # n8n failed - try fallback (index locally)
                logger.warning(f"n8n webhook returned status {response.status_code}. Attempting local fallback...")
                return await _upload_fallback(doc, file.filename, file_content, background_tasks, db)
                
    except httpx.TimeoutException:
        logger.warning("Timeout connecting to n8n webhook. Attempting local fallback...")
        return await _upload_fallback(doc, file.filename, file_content, background_tasks, db)
        
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning(f"Connection error to n8n: {str(e)}. Attempting local fallback...")
        return await _upload_fallback(doc, file.filename, file_content, background_tasks, db)


async def _upload_fallback(doc, filename: str, file_content: bytes, background_tasks: BackgroundTasks, db: Session) -> dict:
    """Fallback upload: save document and index in ChromaDB without n8n."""
    try:
        # Index document in vector store
        vs = get_vector_store()
        chunks_added = await vs.add_document(doc.id, filename, file_content)
        
        # Update document status
        doc.status = "processed"
        db.commit()
        
        # Trigger summary generation in background
        background_tasks.add_task(generate_summary_for_document, doc.id)
        
        logger.info(f"Document {filename} indexed locally (fallback). {chunks_added} chunks added.")
        
        return {
            "success": True,
            "message": f"Document '{filename}' uploaded and indexed locally (n8n unavailable)",
            "filename": filename,
            "document_id": doc.id,
            "chunks_indexed": chunks_added,
            "fallback": True
        }
    except Exception as e:
        doc.status = "error"
        db.commit()
        logger.error(f"Fallback upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document locally: {str(e)}"
        )

@app.post("/api/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload one or more documents and forward them to n8n workflow.
    Accepts PDF, CSV, JSON, and TXT files.
    Supports batch upload - if multiple files are provided, they will be processed sequentially.
    Automatically triggers summary generation after upload.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        results = []
        errors = []
        
        # Process files sequentially (can be parallelized later if needed)
        for file in files:
            try:
                result = await upload_single_file(file, db, background_tasks)
                results.append(result)
                
                # Trigger summary generation for successfully uploaded documents
                if result.get("document_id"):
                    background_tasks.add_task(
                        generate_summary_for_document,
                        result["document_id"]
                    )
                    logger.info(f"Summary generation scheduled for document {result['document_id']}")
                    
            except HTTPException as e:
                errors.append({
                    "filename": file.filename,
                    "error": e.detail
                })
            except Exception as e:
                logger.error(f"Error uploading {file.filename}: {str(e)}", exc_info=True)
                errors.append({
                    "filename": file.filename,
                    "error": f"Internal server error: {str(e)}"
                })
        
        # Return results
        if errors and not results:
            # All files failed
            raise HTTPException(status_code=400, detail=f"All uploads failed: {errors}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Processed {len(results)} file(s) successfully",
                "results": results,
                "errors": errors if errors else None
            }
        )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading documents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# ============ Document Summary Generation ============

async def generate_summary_for_document(document_id: int, retry_delay: int = 30):
    """
    Background task to generate summary for a document.
    Tries n8n webhook first, then falls back to chat-based approach.
    Handles exceptions gracefully and retries on failure.
    """
    # Create new database session for background task
    db = SessionLocal()
    
    try:
        doc = get_document(db, document_id)
        if not doc:
            logger.warning(f"Document {document_id} not found for summary generation")
            return
        
        # Skip if already completed
        if doc.summary_status == "completed" and doc.summary:
            logger.info(f"Document {document_id} already has summary, skipping")
            return
        
        # Check retry count
        max_retries = 3
        if (doc.summary_retry_count or 0) >= max_retries:
            logger.warning(f"Document {document_id} exceeded max retries ({max_retries})")
            return
        
        # Update status to generating
        update_document_summary(db, document_id, summary_status="generating")
        logger.info(f"Generating summary for document {document_id}: {doc.filename}")
        
        summary = None
        error_message = None
        
        # Approach 1: Try n8n summary webhook if configured
        if N8N_SUMMARY_WEBHOOK_ID:
            try:
                summary = await generate_summary_via_n8n(doc.filename, document_id)
                if summary:
                    logger.info(f"Summary generated via n8n for document {document_id}")
            except Exception as e:
                logger.warning(f"n8n summary webhook failed for document {document_id}: {str(e)}")
                error_message = f"n8n webhook: {str(e)}"
        
        # Approach 2: Try chat-based summary generation
        if not summary:
            try:
                summary = await generate_summary_via_chat(doc.filename, document_id)
                if summary:
                    logger.info(f"Summary generated via chat for document {document_id}")
            except Exception as e:
                logger.warning(f"Chat-based summary failed for document {document_id}: {str(e)}")
                error_message = f"Chat fallback: {str(e)}"
        
        # Approach 3: Generate basic summary from filename
        if not summary:
            try:
                summary = generate_basic_summary(doc.filename, doc.file_type, doc.file_size)
                logger.info(f"Basic summary generated for document {document_id}")
            except Exception as e:
                logger.warning(f"Basic summary failed for document {document_id}: {str(e)}")
                error_message = f"Basic summary: {str(e)}"
        
        # Update document with result
        if summary:
            update_document_summary(
                db, document_id,
                summary=summary,
                summary_status="completed",
                summary_error=None
            )
            logger.info(f"Summary saved for document {document_id}")
        else:
            # Mark as failed and schedule retry
            update_document_summary(
                db, document_id,
                summary_status="failed",
                summary_error=error_message or "Unknown error",
                increment_retry=True
            )
            logger.warning(f"Summary generation failed for document {document_id}, will retry later")
            
            # Schedule retry after delay
            await asyncio.sleep(retry_delay)
            # Recursive retry with exponential backoff
            await generate_summary_for_document(document_id, retry_delay * 2)
            
    except Exception as e:
        logger.error(f"Error in summary generation for document {document_id}: {str(e)}", exc_info=True)
        try:
            update_document_summary(
                db, document_id,
                summary_status="failed",
                summary_error=str(e),
                increment_retry=True
            )
        except:
            pass
    finally:
        db.close()


async def generate_summary_via_n8n(filename: str, document_id: int) -> Optional[str]:
    """Generate summary using n8n summary webhook."""
    if not N8N_SUMMARY_WEBHOOK_ID:
        return None
    
    webhook_url = f"{N8N_BASE_URL}/webhook/{N8N_SUMMARY_WEBHOOK_ID}"
    payload = {
        "filename": filename,
        "document_id": document_id,
        "action": "summarize"
    }
    
    auth = None
    if N8N_BASIC_AUTH_USER and N8N_BASIC_AUTH_PASSWORD:
        auth = (N8N_BASIC_AUTH_USER, N8N_BASIC_AUTH_PASSWORD)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        if auth:
            response = await client.post(webhook_url, json=payload, auth=auth)
        else:
            response = await client.post(webhook_url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                return data.get("summary") or data.get("output") or data.get("text")
            elif isinstance(data, str):
                return data
    
    return None


async def generate_summary_via_chat(filename: str, document_id: int) -> Optional[str]:
    """Generate summary by asking the chat AI to summarize the document."""
    webhook_url = f"{N8N_BASE_URL}/webhook/{N8N_CHAT_WEBHOOK_PATH}"
    
    prompt = f"Please provide a brief 2-3 sentence summary of the document '{filename}'. Focus on the main topic and key points."
    
    payload = {
        "chatInput": prompt,
        "message": prompt,
        "input": prompt,
        "document_id": document_id
    }
    
    auth = None
    if N8N_BASIC_AUTH_USER and N8N_BASIC_AUTH_PASSWORD:
        auth = (N8N_BASIC_AUTH_USER, N8N_BASIC_AUTH_PASSWORD)
    
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            if auth:
                response = await client.post(webhook_url, json=payload, auth=auth)
            else:
                response = await client.post(webhook_url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    summary = (
                        data.get("output") or
                        data.get("response") or
                        data.get("text") or
                        data.get("answer") or
                        data.get("message")
                    )
                    if summary and len(summary) > 10:
                        # Clean up the summary
                        summary = summary.strip()
                        # Limit length
                        if len(summary) > 500:
                            summary = summary[:497] + "..."
                        return summary
                elif isinstance(data, str) and len(data) > 10:
                    return data[:500]
    except Exception as e:
        logger.warning(f"Chat summary request failed: {str(e)}")
    
    return None


def generate_basic_summary(filename: str, file_type: str, file_size: int) -> str:
    """Generate a basic summary from file metadata when AI is unavailable."""
    size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"
    
    type_descriptions = {
        "pdf": "PDF document",
        "csv": "spreadsheet data file",
        "json": "structured data file",
        "txt": "text document"
    }
    
    type_desc = type_descriptions.get(file_type.lower(), "document")
    name_without_ext = filename.rsplit(".", 1)[0] if "." in filename else filename
    
    return f"This is a {type_desc} named '{name_without_ext}' ({size_str}). Upload and process complete - ready for analysis."


@app.post("/api/documents/{document_id}/generate-summary")
async def trigger_summary_generation(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger summary generation for a document."""
    try:
        doc = get_document(db, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        # Reset retry count for manual trigger
        update_document_summary(
            db, document_id,
            summary_status="pending",
            summary_error=None
        )
        # Reset retry count manually
        doc.summary_retry_count = 0
        db.commit()
        
        # Add background task
        background_tasks.add_task(generate_summary_for_document, document_id)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Summary generation started for document {document_id}",
                "document_id": document_id
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/generate-all-summaries")
async def trigger_all_summaries(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger summary generation for all pending documents."""
    try:
        pending_docs = get_documents_pending_summary(db)
        
        for doc in pending_docs:
            background_tasks.add_task(generate_summary_for_document, doc.id)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Summary generation started for {len(pending_docs)} documents",
                "document_ids": [d.id for d in pending_docs]
            }
        )
    except Exception as e:
        logger.error(f"Error triggering summaries: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



def extract_sources_from_response(response_text: str, db: Session) -> List[int]:
    """Extract document IDs from AI response if it mentions document names."""
    # This is a simple implementation - can be enhanced with better parsing
    # For now, we'll try to match document filenames mentioned in the response
    sources = []
    try:
        # Get all documents
        documents = get_documents(db, skip=0, limit=1000)
        for doc in documents:
            # Check if document filename is mentioned in response
            if doc.filename.lower() in response_text.lower():
                sources.append(doc.id)
    except Exception as e:
        logger.warning(f"Error extracting sources: {str(e)}")
    return sources

@app.post("/api/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Send a chat message to the AI agent and get a response.
    PRIMARY: LangGraph agent (local RAG with Groq)
    FALLBACK: n8n webhook (if LangGraph fails or is unavailable)
    Stores messages in database and supports conversation history.
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Get or create conversation
        conversation = None
        if request.conversation_id:
            conversation = get_conversation(db, request.conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail=f"Conversation {request.conversation_id} not found")
        else:
            # Create new conversation
            conversation = create_conversation(db)
        
        # Store user message
        user_message = create_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.message
        )
        
        ai_response = None
        sources = []
        used_fallback = False
        
        # ============ PRIMARY: LangGraph Agent ============
        if is_langgraph_available():
            logger.info("Using LangGraph as primary AI backend...")
            try:
                # Get conversation history
                history = get_messages(db, conversation_id=conversation.id, limit=10)
                history_dicts = [{"role": m.role, "content": m.content} for m in history][::-1]
                
                # Run LangGraph Agent
                result = await run_agent(
                    query=request.message,
                    conversation_history=history_dicts
                )
                
                if not result.error:
                    ai_response = result.content
                    sources = result.sources if result.sources else []
                    logger.info(f"LangGraph response successful. Length: {len(ai_response)}")
                else:
                    logger.warning(f"LangGraph returned error: {result.error}. Attempting n8n fallback...")
            except Exception as e:
                logger.warning(f"LangGraph execution failed: {e}. Attempting n8n fallback...")
        else:
            logger.info("LangGraph not available. Using n8n as fallback...")
        
        # ============ FALLBACK: n8n Webhook ============
        if ai_response is None:
            used_fallback = True
            logger.info("Attempting n8n fallback...")
            
            webhook_url = f"{N8N_BASE_URL}/webhook/{N8N_CHAT_WEBHOOK_PATH}"
            
            payload = {
                "chatInput": request.message,
                "message": request.message,
                "input": request.message,
                "conversation_id": conversation.id
            }
            
            # Prepare auth if basic auth is enabled
            auth = None
            if N8N_BASIC_AUTH_USER and N8N_BASIC_AUTH_PASSWORD:
                auth = (N8N_BASIC_AUTH_USER, N8N_BASIC_AUTH_PASSWORD)
            
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    if auth:
                        response = await client.post(webhook_url, json=payload, auth=auth)
                    else:
                        response = await client.post(webhook_url, json=payload)
                    
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            if isinstance(response_data, dict):
                                ai_response = (
                                    response_data.get("output") or
                                    response_data.get("response") or
                                    response_data.get("text") or
                                    response_data.get("answer") or
                                    response_data.get("message") or
                                    response_data.get("result") or
                                    str(response_data)
                                )
                                sources_data = response_data.get("sources", [])
                                if isinstance(sources_data, list):
                                    sources = sources_data
                                else:
                                    sources = extract_sources_from_response(str(ai_response), db)
                            elif isinstance(response_data, list) and len(response_data) > 0:
                                ai_response = str(response_data[0])
                                sources = extract_sources_from_response(str(ai_response), db)
                            else:
                                ai_response = str(response_data)
                                sources = extract_sources_from_response(str(ai_response), db)
                        except:
                            ai_response = response.text.strip() if response.text else ""
                            sources = extract_sources_from_response(ai_response, db) if ai_response else []
                        
                        if ai_response:
                            ai_response += "\n\n*(answered via n8n fallback)*"
                            logger.info(f"n8n fallback response successful. Length: {len(ai_response)}")
                    else:
                        logger.error(f"n8n fallback also failed with status {response.status_code}")
                        
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.error(f"n8n fallback connection failed: {e}")
        
        # ============ FINAL RESPONSE ============
        if ai_response:
            # Extract document IDs for database linking
            source_ids = []
            if sources:
                # Pre-fetch all documents to look up IDs by filename
                # (Optimization: could be a specific query but this is safer/easier for now)
                try:
                    all_docs = get_documents(db, limit=1000)
                    filename_to_id = {d.filename: d.id for d in all_docs}
                    
                    for source in sources:
                        if isinstance(source, dict):
                            if "id" in source:
                                source_ids.append(source["id"])
                            elif "filename" in source:
                                # Loose matching for filename (checking if one contains the other)
                                src_name = source["filename"]
                                if src_name in filename_to_id:
                                    source_ids.append(filename_to_id[src_name])
                                else:
                                    # Try partial match (case insensitive)
                                    for db_name, db_id in filename_to_id.items():
                                        if src_name.lower() in db_name.lower() or db_name.lower() in src_name.lower():
                                            source_ids.append(db_id)
                                            break
                        elif isinstance(source, int):
                            source_ids.append(source)
                except Exception as e:
                    logger.warning(f"Error mapping sources to IDs: {e}")
            
            # Store assistant message
            assistant_message = create_message(
                db=db,
                conversation_id=conversation.id,
                role="assistant",
                content=ai_response,
                sources=source_ids
            )
            
            # Get source document metadata if sources are document IDs
            source_docs = []
            if sources:
                for source in sources:
                    if isinstance(source, int):
                        doc = get_document(db, source)
                        if doc:
                            source_docs.append({
                                "id": doc.id,
                                "filename": doc.filename,
                                "file_type": doc.file_type
                            })
                    elif isinstance(source, dict):
                        source_docs.append(source)
            
            logger.info(f"Chat response completed. Length: {len(str(ai_response))}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "response": ai_response,
                    "conversation_id": conversation.id,
                    "message_id": assistant_message.id,
                    "sources": source_docs
                }
            )
        else:
            # Both LangGraph and n8n failed
            error_message = "I apologize, but I'm currently unable to process your request. Both the primary AI system (LangGraph) and backup system (n8n) are unavailable. Please check:\n\n1. **GROQ_API_KEY** is set in your .env file\n2. **n8n** is running at the configured URL\n\nTry again in a moment."
            
            assistant_message = create_message(
                db=db,
                conversation_id=conversation.id,
                role="assistant",
                content=error_message
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "response": error_message,
                    "conversation_id": conversation.id,
                    "message_id": assistant_message.id,
                    "sources": []
                }
            )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Stream chat responses in real-time using Server-Sent Events (SSE).
    Stores messages in database and supports conversation history.
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Get or create conversation
        conversation = None
        if request.conversation_id:
            conversation = get_conversation(db, request.conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail=f"Conversation {request.conversation_id} not found")
        else:
            conversation = create_conversation(db)
        
        # Store user message
        user_message = create_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.message
        )
        
        async def generate():
            """Generator function for streaming responses."""
            webhook_url = f"{N8N_BASE_URL}/webhook/{N8N_CHAT_WEBHOOK_PATH}"
            payload = {
                "chatInput": request.message,
                "message": request.message,
                "input": request.message,
                "conversation_id": conversation.id
            }
            
            auth = None
            if N8N_BASIC_AUTH_USER and N8N_BASIC_AUTH_PASSWORD:
                auth = (N8N_BASIC_AUTH_USER, N8N_BASIC_AUTH_PASSWORD)
            
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    if auth:
                        response = await client.post(webhook_url, json=payload, auth=auth)
                    else:
                        response = await client.post(webhook_url, json=payload)
                    
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            if isinstance(response_data, dict):
                                ai_response = (
                                    response_data.get("output") or
                                    response_data.get("response") or
                                    response_data.get("text") or
                                    response_data.get("answer") or
                                    response_data.get("message") or
                                    response_data.get("result") or
                                    str(response_data)
                                )
                                sources_data = response_data.get("sources", [])
                                sources = sources_data if isinstance(sources_data, list) else extract_sources_from_response(str(ai_response), db)
                            else:
                                ai_response = str(response_data)
                                sources = extract_sources_from_response(ai_response, db)
                        except:
                            ai_response = response.text.strip() if response.text else ""
                            sources = extract_sources_from_response(ai_response, db) if ai_response else []
                        
                        if not ai_response or (isinstance(ai_response, str) and len(ai_response.strip()) == 0):
                            ai_response = f"I received your message: '{request.message}'. The webhook connection works (HTTP 200), but the AI Agent returned an empty response."
                            sources = []
                        
                        # Stream the response word by word for better performance
                        words = ai_response.split()
                        full_response = ""
                        for i, word in enumerate(words):
                            full_response += word + (" " if i < len(words) - 1 else "")
                            # Send SSE formatted data
                            chunk_data = json.dumps({"chunk": word + " ", "done": False})
                            yield f"data: {chunk_data}\n\n"
                        
                        # Store complete assistant message
                        assistant_message = create_message(
                            db=db,
                            conversation_id=conversation.id,
                            role="assistant",
                            content=full_response,
                            sources=sources
                        )
                        
                        # Get source document metadata
                        source_docs = []
                        for doc_id in sources:
                            doc = get_document(db, doc_id)
                            if doc:
                                source_docs.append({
                                    "id": doc.id,
                                    "filename": doc.filename,
                                    "file_type": doc.file_type
                                })
                        
                        # Send final message with metadata
                        final_data = {
                            "chunk": "",
                            "done": True,
                            "conversation_id": conversation.id,
                            "message_id": assistant_message.id,
                            "sources": source_docs
                        }
                        yield f"data: {json.dumps(final_data)}\n\n"
                    else:
                        error_msg = f"Error: n8n returned status {response.status_code}"
                        yield f"data: {json.dumps({'chunk': error_msg, 'done': True, 'error': True})}\n\n"
            except Exception as e:
                logger.error(f"Error in streaming: {str(e)}", exc_info=True)
                error_msg = f"Error: {str(e)}"
                yield f"data: {json.dumps({'chunk': error_msg, 'done': True, 'error': True})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat stream: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Catch-all route for SPA routing - must be last
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """
    Serve the React app for all non-API routes.
    This enables client-side routing.
    """
    # Don't serve index.html for API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Serve index.html for all other routes (SPA routing)
    if FRONTEND_DIST.exists():
        index_path = FRONTEND_DIST / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
    
    raise HTTPException(status_code=404, detail="Not found")

if __name__ == "__main__":
    import uvicorn
    # Use port 8000 (standard port)
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

