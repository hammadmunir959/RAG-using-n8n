"""
ChromaDB Vector Store for document embeddings.
Provides semantic search across uploaded documents.
"""
import logging
import os
from typing import List, Optional, Dict, Any
from pathlib import Path

import chromadb
from chromadb.config import Settings

from document_processors import extract_text, chunk_text

logger = logging.getLogger(__name__)

# Embedding model - lightweight and fast
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


class SentenceTransformerEmbeddings:
    """Wrapper for sentence-transformers embeddings compatible with ChromaDB."""
    
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None
    
    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info("Embedding model loaded successfully")
            except ImportError:
                raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")
        return self._model
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.model.encode(input, show_progress_bar=False)
        return embeddings.tolist()


def get_embedding_function():
    """Get the embedding function for ChromaDB."""
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    except ImportError:
        # Fallback to custom implementation
        return SentenceTransformerEmbeddings()


class VectorStore:
    """
    ChromaDB-based vector store for document retrieval.
    
    Features:
    - Persistent storage in data/chromadb/
    - Semantic similarity search
    - Document-level operations (add, search, delete)
    """
    
    def __init__(self, persist_path: Optional[str] = None):
        """
        Initialize the vector store.
        
        Args:
            persist_path: Directory to store ChromaDB data. Defaults to ./data/chromadb/
        """
        if persist_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            persist_path = str(base_dir / "data" / "chromadb")
        
        # Ensure directory exists
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing ChromaDB at: {persist_path}")
        
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Initialize embedding function
        self.embedding_fn = get_embedding_function()
        
        # Get or create the documents collection
        self.collection = self.client.get_or_create_collection(
            name="documents",
            embedding_function=self.embedding_fn,
            metadata={"description": "Document chunks for RAG"}
        )
        
        logger.info(f"Vector store initialized. Collection has {self.collection.count()} chunks.")
    
    async def add_document(
        self,
        doc_id: int,
        filename: str,
        content: bytes,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> int:
        """
        Process and add a document to the vector store.
        
        Args:
            doc_id: Database document ID
            filename: Original filename
            content: Raw file bytes
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            
        Returns:
            Number of chunks added
        """
        try:
            # Extract text from document
            logger.info(f"Extracting text from: {filename}")
            text = extract_text(filename, content)
            
            if not text or not text.strip():
                logger.warning(f"No text extracted from {filename}")
                return 0
            
            # Chunk the text
            chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            logger.info(f"Split into {len(chunks)} chunks")
            
            if not chunks:
                return 0
            
            # Prepare data for ChromaDB
            ids = [f"doc_{doc_id}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "doc_id": doc_id,
                    "filename": filename,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
                for i in range(len(chunks))
            ]
            
            # Add to collection
            self.collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(chunks)} chunks for document {doc_id}: {filename}")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Error adding document {doc_id} to vector store: {e}")
            raise
    
    def search(
        self,
        query: str,
        k: int = 5,
        score_threshold: float = 0.3,
        doc_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant document chunks.
        
        Args:
            query: Search query
            k: Maximum number of results
            score_threshold: Minimum similarity score (0-1, higher is more similar)
            doc_ids: Optional list of document IDs to filter
            
        Returns:
            List of results with text, metadata, and scores
        """
        try:
            # Build where filter if doc_ids specified
            where_filter = None
            if doc_ids:
                where_filter = {"doc_id": {"$in": doc_ids}}
            
            # Query the collection
            results = self.collection.query(
                query_texts=[query],
                n_results=k,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
            
            if not results or not results['documents'] or not results['documents'][0]:
                return []
            
            # Process results
            processed = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                # Convert distance to similarity score (ChromaDB uses L2 distance)
                # Lower distance = higher similarity
                # Normalize roughly to 0-1 range
                similarity = 1 / (1 + distance)
                
                if similarity >= score_threshold:
                    processed.append({
                        "text": doc,
                        "metadata": metadata,
                        "score": round(similarity, 4),
                        "doc_id": metadata.get("doc_id"),
                        "filename": metadata.get("filename"),
                        "chunk_index": metadata.get("chunk_index")
                    })
            
            # Sort by score descending
            processed.sort(key=lambda x: x["score"], reverse=True)
            
            logger.info(f"Search returned {len(processed)} results for query: {query[:50]}...")
            return processed
            
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    def delete_document(self, doc_id: int) -> int:
        """
        Delete all chunks for a document.
        
        Args:
            doc_id: Database document ID
            
        Returns:
            Number of chunks deleted
        """
        try:
            # Find all chunks for this document
            results = self.collection.get(
                where={"doc_id": doc_id},
                include=["metadatas"]
            )
            
            if not results or not results['ids']:
                logger.info(f"No chunks found for document {doc_id}")
                return 0
            
            chunk_ids = results['ids']
            
            # Delete the chunks
            self.collection.delete(ids=chunk_ids)
            
            logger.info(f"Deleted {len(chunk_ids)} chunks for document {doc_id}")
            return len(chunk_ids)
            
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from vector store: {e}")
            return 0
    
    def get_document_chunks(self, doc_id: int) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document."""
        try:
            results = self.collection.get(
                where={"doc_id": doc_id},
                include=["documents", "metadatas"]
            )
            
            if not results or not results['documents']:
                return []
            
            return [
                {
                    "id": id,
                    "text": doc,
                    "metadata": meta
                }
                for id, doc, meta in zip(
                    results['ids'],
                    results['documents'],
                    results['metadatas']
                )
            ]
        except Exception as e:
            logger.error(f"Error getting chunks for document {doc_id}: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        try:
            count = self.collection.count()
            
            # Get unique document count
            if count > 0:
                results = self.collection.get(include=["metadatas"])
                doc_ids = set(m.get("doc_id") for m in results['metadatas'] if m)
                unique_docs = len(doc_ids)
            else:
                unique_docs = 0
            
            return {
                "total_chunks": count,
                "unique_documents": unique_docs,
                "collection_name": self.collection.name
            }
        except Exception as e:
            logger.error(f"Error getting vector store stats: {e}")
            return {"error": str(e)}
    
    def clear(self) -> bool:
        """Clear all documents from the vector store."""
        try:
            self.client.delete_collection("documents")
            self.collection = self.client.get_or_create_collection(
                name="documents",
                embedding_function=self.embedding_fn,
                metadata={"description": "Document chunks for RAG"}
            )
            logger.info("Vector store cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing vector store: {e}")
            return False


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def init_vector_store() -> VectorStore:
    """Initialize the vector store (call on startup)."""
    return get_vector_store()
