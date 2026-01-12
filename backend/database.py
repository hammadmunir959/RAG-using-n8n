"""
Database models and operations for Document Intelligence WebApp.
Uses SQLite with SQLAlchemy ORM for persistence.
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, JSON, Index, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import List, Optional
import os
import logging
from pathlib import Path
from contextlib import contextmanager

Base = declarative_base()


class Document(Base):
    """Document metadata model."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, index=True)
    file_type = Column(String, nullable=False)  # pdf, csv, json, txt
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    status = Column(String, default="uploaded")  # uploaded, processing, processed, error
    meta_data = Column(JSON, default=dict)  # Additional metadata as JSON (renamed from metadata to avoid SQLAlchemy conflict)
    
    # Summary fields
    summary = Column(Text, nullable=True)  # Auto-generated document summary
    summary_status = Column(String, default="pending")  # pending, generating, completed, failed
    summary_retry_count = Column(Integer, default=0)  # Number of retry attempts
    summary_error = Column(Text, nullable=True)  # Last error message if failed
    
    # Relationships
    messages = relationship("Message", back_populates="sources_documents", secondary="message_sources")


class Conversation(Base):
    """Conversation model for chat history."""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)  # Auto-generated from first message
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    """Chat message model."""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    sources = Column(JSON, default=list)  # List of document IDs referenced in this message
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sources_documents = relationship("Document", secondary="message_sources", back_populates="messages")


# Association table for many-to-many relationship between messages and documents
message_sources = Table(
    "message_sources",
    Base.metadata,
    Column("message_id", Integer, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
)


# Database setup
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "data"
DATABASE_DIR.mkdir(exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_DIR / 'app.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def cleanup_db():
    """Cleanup database connections on shutdown."""
    engine.dispose()
    logger = logging.getLogger(__name__)
    logger.info("Database connections closed")


def init_db():
    """Initialize database and create all tables."""
    Base.metadata.create_all(bind=engine)
    # Create indexes for better query performance
    Index("idx_documents_filename", Document.filename).create(engine, checkfirst=True)
    Index("idx_documents_upload_date", Document.upload_date).create(engine, checkfirst=True)
    Index("idx_conversations_created_at", Conversation.created_at).create(engine, checkfirst=True)
    Index("idx_messages_conversation_id", Message.conversation_id).create(engine, checkfirst=True)
    Index("idx_messages_created_at", Message.created_at).create(engine, checkfirst=True)


def get_db():
    """Dependency for getting database session with proper cleanup."""
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit successful transactions
    except Exception:
        db.rollback()  # Rollback on any exception
        raise
    finally:
        db.close()  # Always close the session


@contextmanager
def get_db_context():
    """Context manager for database sessions with proper cleanup."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# CRUD Operations

def create_document(
    db: Session,
    filename: str,
    file_type: str,
    file_size: int,
    status: str = "uploaded",
    metadata: Optional[dict] = None
) -> Document:
    """Create a new document record."""
    try:
        doc = Document(
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            status=status,
            meta_data=metadata or {}
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
    except Exception:
        db.rollback()
        raise


def get_document(db: Session, document_id: int) -> Optional[Document]:
    """Get a document by ID."""
    return db.query(Document).filter(Document.id == document_id).first()


def get_documents(db: Session, skip: int = 0, limit: int = 100) -> List[Document]:
    """Get all documents with pagination."""
    return db.query(Document).order_by(Document.upload_date.desc()).offset(skip).limit(limit).all()


def delete_document(db: Session, document_id: int) -> bool:
    """Delete a document by ID."""
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            db.delete(doc)
            db.commit()
            return True
        return False
    except Exception:
        db.rollback()
        raise


def create_conversation(db: Session, title: Optional[str] = None) -> Conversation:
    """Create a new conversation."""
    try:
        conv = Conversation(title=title)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return conv
    except Exception:
        db.rollback()
        raise


def get_conversation(db: Session, conversation_id: int) -> Optional[Conversation]:
    """Get a conversation by ID with messages."""
    return db.query(Conversation).filter(Conversation.id == conversation_id).first()


def get_conversations(db: Session, skip: int = 0, limit: int = 100) -> List[Conversation]:
    """Get all conversations with pagination."""
    return db.query(Conversation).order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()


def delete_conversation(db: Session, conversation_id: int) -> bool:
    """Delete a conversation by ID (cascades to messages)."""
    try:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv:
            db.delete(conv)
            db.commit()
            return True
        return False
    except Exception:
        db.rollback()
        raise


def update_conversation_title(db: Session, conversation_id: int, title: str) -> Optional[Conversation]:
    """Update conversation title."""
    try:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv:
            conv.title = title
            conv.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(conv)
        return conv
    except Exception:
        db.rollback()
        raise


def create_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    sources: Optional[List[int]] = None
) -> Message:
    """Create a new message."""
    try:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources or []
        )
        db.add(message)
        
        # Link to source documents if provided
        if sources:
            for doc_id in sources:
                doc = get_document(db, doc_id)
                if doc:
                    message.sources_documents.append(doc)
        
        db.commit()
        db.refresh(message)
        
        # Auto-generate conversation title from first user message if not set
        conv = get_conversation(db, conversation_id)
        if conv and not conv.title and role == "user":
            try:
                title = content[:50] + "..." if len(content) > 50 else content
                conv.title = title
                db.commit()
            except Exception as e:
                db.rollback()
                # Don't fail message creation if title update fails
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to update conversation title: {str(e)}")
        
        return message
    except Exception:
        db.rollback()
        raise


def get_messages(db: Session, conversation_id: int, limit: int = None) -> List[Message]:
    """Get all messages for a conversation."""
    query = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at)
    if limit:
        query = query.limit(limit)
    return query.all()


def update_document_summary(
    db: Session,
    document_id: int,
    summary: Optional[str] = None,
    summary_status: str = "pending",
    summary_error: Optional[str] = None,
    increment_retry: bool = False
) -> Optional[Document]:
    """Update document summary fields."""
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            if summary is not None:
                doc.summary = summary
            doc.summary_status = summary_status
            if summary_error is not None:
                doc.summary_error = summary_error
            if increment_retry:
                doc.summary_retry_count = (doc.summary_retry_count or 0) + 1
            db.commit()
            db.refresh(doc)
        return doc
    except Exception:
        db.rollback()
        raise


def get_documents_pending_summary(db: Session, max_retries: int = 3) -> List[Document]:
    """Get documents that need summary generation."""
    return db.query(Document).filter(
        Document.summary_status.in_(["pending", "failed"]),
        Document.summary_retry_count < max_retries
    ).order_by(Document.upload_date.desc()).all()
