from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx
import os
from pathlib import Path
from typing import Optional, List, Tuple
from pydantic import BaseModel
import logging
import json
from sqlalchemy.orm import Session
from database import (
    init_db, get_db, cleanup_db, create_document, get_document, get_documents, delete_document,
    create_conversation, get_conversation, get_conversations, delete_conversation,
    update_conversation_title, create_message, get_messages
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Intelligence API")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    logger.info("Database initialized")


# Cleanup database connections on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    cleanup_db()
    logger.info("Application shutdown - database connections closed")

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
    """List all uploaded documents with metadata."""
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
                        "metadata": doc.meta_data
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

async def upload_single_file(file: UploadFile, db: Session) -> dict:
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
    
    # Prepare form data for n8n webhook
    files = {
        "Upload_Document": (file.filename, file_content, normalized_content_type)
    }
    
    # Forward to n8n webhook
    webhook_url = f"{N8N_BASE_URL}/webhook/{N8N_UPLOAD_WEBHOOK_ID}"
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
                logger.info(f"Document {file.filename} uploaded successfully")
                return {
                    "success": True,
                    "message": f"Document '{file.filename}' uploaded and processed successfully",
                    "filename": file.filename,
                    "document_id": doc.id
                }
            else:
                # Update document status to error
                doc.status = "error"
                db.commit()
                error_text = response.text[:500]
                logger.error(f"n8n webhook returned status {response.status_code}: {error_text}")
                
                # Check for specific n8n errors
                try:
                    error_json = response.json()
                    if error_json.get("code") == 404 and "not registered" in error_json.get("message", ""):
                        raise HTTPException(
                            status_code=503,
                            detail="n8n upload workflow is not active. Please activate the upload workflow in n8n (toggle in top-right of editor)."
                        )
                except HTTPException:
                    raise
                except:
                    pass
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to process document: {error_text}"
                )
    except httpx.TimeoutException:
        doc.status = "error"
        db.commit()
        logger.error("Timeout connecting to n8n webhook")
        raise HTTPException(
            status_code=504,
            detail="Request to n8n timed out. Please try again."
        )
    except httpx.ConnectError as e:
        doc.status = "error"
        db.commit()
        logger.error(f"Connection error to n8n: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to n8n. Make sure n8n is running at {N8N_BASE_URL}"
        )

@app.post("/api/upload")
async def upload_document(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload one or more documents and forward them to n8n workflow.
    Accepts PDF, CSV, JSON, and TXT files.
    Supports batch upload - if multiple files are provided, they will be processed sequentially.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        results = []
        errors = []
        
        # Process files sequentially (can be parallelized later if needed)
        for file in files:
            try:
                result = await upload_single_file(file, db)
                results.append(result)
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
        
        # Forward to n8n chat webhook
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
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                if auth:
                    response = await client.post(webhook_url, json=payload, auth=auth)
                else:
                    response = await client.post(webhook_url, json=payload)
            except httpx.ConnectError as e:
                logger.error(f"Connection error to n8n: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Cannot connect to n8n. Make sure n8n is running at {N8N_BASE_URL}"
                )
            
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
                        # Try to extract sources from response data
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
                
                # Check if response is empty
                if not ai_response or (isinstance(ai_response, str) and len(ai_response.strip()) == 0):
                    logger.warning(f"AI Agent returned empty response")
                    ai_response = f"I received your message: '{request.message}'. The webhook connection works (HTTP 200), but the AI Agent returned an empty response."
                    sources = []
                
                # Store assistant message
                assistant_message = create_message(
                    db=db,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=ai_response,
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
                
                logger.info(f"Chat response received successfully, length: {len(str(ai_response))}")
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
            elif response.status_code == 500:
                error_text = response.text
                logger.error(f"n8n workflow execution error: {error_text}")
                try:
                    error_json = response.json()
                    error_msg = error_json.get("message", "Error in workflow")
                except:
                    error_msg = error_text[:200]
                
                error_response = f"I received your message: '{request.message}'. However, there was an error processing it in the n8n workflow. Please check your n8n workflow at http://localhost:5678 for errors. Error: {error_msg[:100]}"
                
                # Store error message
                create_message(
                    db=db,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=error_response
                )
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "response": error_response,
                        "conversation_id": conversation.id,
                        "sources": []
                    }
                )
            else:
                error_text = response.text
                logger.error(f"n8n chat webhook returned status {response.status_code}: {error_text}")
                
                try:
                    error_json = response.json()
                    if error_json.get("code") == 404 and "not registered" in error_json.get("message", ""):
                        error_response = f"I received your message: '{request.message}'. However, the chat workflow is not active. Please:\n\n1. Go to http://localhost:5678\n2. Open your chat workflow\n3. Click the green toggle in the top-right to ACTIVATE the workflow\n4. The webhook path ({N8N_CHAT_WEBHOOK_PATH}) is correct, just needs activation.\n\nOnce activated, the chat will work automatically!"
                        
                        create_message(
                            db=db,
                            conversation_id=conversation.id,
                            role="assistant",
                            content=error_response
                        )
                        
                        return JSONResponse(
                            status_code=200,
                            content={
                                "success": True,
                                "response": error_response,
                                "conversation_id": conversation.id,
                                "sources": []
                            }
                        )
                except (ValueError, KeyError):
                    pass
                except HTTPException:
                    raise
                
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to get chat response: {error_text[:500]}"
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

