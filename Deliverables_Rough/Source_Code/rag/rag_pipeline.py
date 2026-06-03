import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    OPENAI_API_KEY, EMBEDDING_MODEL, CHROMA_PERSIST_DIR,
    DOCUMENTS_DIR, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    AWS_REGION, S3_BUCKET_NAME
)

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, DirectoryLoader

_vectorstore = None


def _load_documents_from_local() -> List:
    if not os.path.exists(DOCUMENTS_DIR):
        return []
    loader = DirectoryLoader(DOCUMENTS_DIR, glob="*.txt", loader_cls=TextLoader)
    documents = loader.load()
    return documents


def _load_documents_from_s3() -> List:
    try:
        import boto3
        import tempfile

        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        documents = []
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="documents/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".txt") or key.endswith(".pdf"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(key)[1]) as tmp:
                        s3.download_fileobj(S3_BUCKET_NAME, key, tmp)
                        tmp_path = tmp.name
                    loader = TextLoader(tmp_path)
                    documents.extend(loader.load())
                    os.unlink(tmp_path)
        return documents
    except Exception as e:
        print(f"[RAG] S3 load failed, falling back to local: {e}")
        return []


def initialize_rag(force_rebuild: bool = False) -> Chroma:
    global _vectorstore

    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=OPENAI_API_KEY
    )

    if not force_rebuild and os.path.exists(CHROMA_PERSIST_DIR):
        _vectorstore = Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=embeddings
        )
        print("[RAG] Loaded existing vector store from disk.")
        return _vectorstore

    print("[RAG] Building new vector store...")
    documents = _load_documents_from_s3()
    if not documents:
        documents = _load_documents_from_local()

    if not documents:
        print("[RAG] Warning: No documents found. RAG will return empty context.")
        _vectorstore = Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=embeddings
        )
        return _vectorstore

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_documents(documents)
    print(f"[RAG] Indexed {len(chunks)} chunks from {len(documents)} documents.")

    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PERSIST_DIR
    )

    return _vectorstore


def get_rag_context(query: str, k: int = 4) -> str:
    global _vectorstore

    if _vectorstore is None:
        initialize_rag()

    if _vectorstore is None:
        return ""

    try:
        results = _vectorstore.similarity_search(query, k=k)
        if not results:
            return ""
        context_parts = [f"[Source: {doc.metadata.get('source', 'Protocol')}]\n{doc.page_content}" for doc in results]
        return "\n\n---\n\n".join(context_parts)
    except Exception as e:
        print(f"[RAG] Retrieval error: {e}")
        return ""
