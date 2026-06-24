"""ChromaDB-based RAG pipeline for medical protocol retrieval."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    GEMINI_API_KEY,
    PROTOCOLS_DIR,
)


logger = logging.getLogger(__name__)


_SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
_vectorstore: Optional[Chroma] = None


def _extract_pdf_text(file_path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n".join(text_parts)
    except Exception as exc:
        logger.warning(f"Failed to extract text from PDF {file_path.name}: {exc}")
        return ""


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks: list[str] = []
    
    if not words:
        return chunks
    
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words).strip())
        
        # Move start forward, accounting for overlap
        start = end - overlap
        if start >= len(words):
            break
    
    return chunks


def _load_protocol_files() -> list[Path]:
    """Load all supported protocol files from the protocols directory."""
    if not PROTOCOLS_DIR.exists():
        return []
    return [
        path
        for path in PROTOCOLS_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in _SUPPORTED_EXTENSIONS
    ]


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Initialize Google Generative AI embeddings."""
    if not GEMINI_API_KEY:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY must be set in environment")
    
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GEMINI_API_KEY
    )


def _initialize_vectorstore() -> Chroma:
    """Initialize or load the ChromaDB vectorstore."""
    global _vectorstore
    
    if _vectorstore is not None:
        return _vectorstore
    
    try:
        # Ensure the persist directory exists
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        
        embeddings = _get_embeddings()
        
        # Initialize ChromaDB client with persistent storage
        client = chromadb.PersistentClient(
            path=str(CHROMA_PERSIST_DIR),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        
        # Initialize Langchain Chroma wrapper
        _vectorstore = Chroma(
            client=client,
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
        )
        
        logger.info(f"ChromaDB vectorstore initialized at {CHROMA_PERSIST_DIR}")
        return _vectorstore
        
    except Exception as exc:
        logger.error(f"Failed to initialize ChromaDB vectorstore: {exc}", exc_info=True)
        raise


def get_vectorstore() -> Chroma:
    """Get the initialized vectorstore instance."""
    return _initialize_vectorstore()


def retrieve_context_chunks(query: str, k: int = 3) -> list[dict]:
    """
    Retrieve relevant context chunks using ChromaDB vector similarity search.
    
    Args:
        query: The search query
        k: Number of top results to return
        
    Returns:
        List of dictionaries containing source, page, and chunk text
    """
    try:
        vectorstore = _initialize_vectorstore()
        
        # Perform similarity search
        results = vectorstore.similarity_search(query, k=k)
        
        if not results:
            logger.warning(f"ChromaDB retrieval returned empty for query: {query}")
            return []
        
        # Format results to match expected structure
        chunks = []
        for doc in results:
            metadata = doc.metadata
            chunks.append({
                "source": metadata.get("source", "unknown"),
                "page": metadata.get("page", 1),
                "chunk": doc.page_content,
            })
        
        return chunks
        
    except Exception as exc:
        logger.error(f"ChromaDB retrieval failed for query '{query}': {exc}", exc_info=True)
        # Fallback to empty results rather than crashing
        return []


def get_rag_context(query: str, k: int = 3) -> str:
    """
    Get formatted RAG context for a query.
    
    Args:
        query: The search query
        k: Number of top results to return
        
    Returns:
        Formatted string with retrieved context chunks
    """
    try:
        chunks = retrieve_context_chunks(query, k=k)
        if not chunks:
            logger.warning(f"No context retrieved for query: {query}")
            return ""
        
        return "\n\n---\n\n".join(
            f"[Source: {chunk['source']} | Page: {chunk['page']}]\n{chunk['chunk']}"
            for chunk in chunks
        )
    except Exception as exc:
        logger.error(f"RAG context retrieval failed for query '{query}': {exc}", exc_info=True)
        return ""


def index_protocols() -> int:
    """
    Index all protocol files into ChromaDB.
    
    Returns:
        Number of chunks indexed
    """
    try:
        vectorstore = _initialize_vectorstore()
        
        # Get existing document IDs to avoid duplicates
        collection = vectorstore._collection
        existing_ids = set(collection.get()["ids"])
        
        protocol_files = _load_protocol_files()
        if not protocol_files:
            logger.warning(f"No protocol files found in {PROTOCOLS_DIR}")
            return 0
        
        documents = []
        total_chunks = 0
        
        for file_path in protocol_files:
            try:
                # Extract text based on file type
                if file_path.suffix.lower() == ".pdf":
                    content = _extract_pdf_text(file_path)
                else:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                
                if not content:
                    logger.warning(f"No content extracted from {file_path.name}")
                    continue
                
                # Chunk the content
                chunks = _chunk_text(content)
                
                # Create documents with metadata
                for idx, chunk in enumerate(chunks):
                    doc_id = f"{file_path.stem}_{idx}"
                    
                    # Skip if already indexed
                    if doc_id in existing_ids:
                        continue
                    
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            "source": file_path.name,
                            "page": idx + 1,
                            "file_path": str(file_path),
                        },
                    )
                    documents.append(doc)
                    total_chunks += 1
                
                logger.info(f"Processed {file_path.name}: {len(chunks)} chunks")
                
            except Exception as exc:
                logger.error(f"Failed to process {file_path.name}: {exc}")
                continue
        
        # Add documents to vectorstore
        if documents:
            vectorstore.add_documents(documents)
            logger.info(f"Successfully indexed {total_chunks} new chunks from {len(protocol_files)} files")
        else:
            logger.info("No new documents to index (all already present)")
        
        return total_chunks
        
    except Exception as exc:
        logger.error(f"Failed to index protocols: {exc}", exc_info=True)
        raise


def reset_vectorstore() -> None:
    """Reset the vectorstore by deleting all data."""
    global _vectorstore
    
    try:
        if _vectorstore is not None:
            _vectorstore._collection.delete()
            _vectorstore = None
        
        # Also clear the persistent directory
        if CHROMA_PERSIST_DIR.exists():
            import shutil
            shutil.rmtree(CHROMA_PERSIST_DIR)
            CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info("Vectorstore reset successfully")
        
    except Exception as exc:
        logger.error(f"Failed to reset vectorstore: {exc}", exc_info=True)
        raise

# Made with Bob
