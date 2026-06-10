"""Local RAG helper used by the workflow."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from src.config import PROTOCOLS_DIR


_SUPPORTED_EXTENSIONS = {".txt", ".md"}


def _chunk_text(text: str, chunk_size: int = 700) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        current.append(word)
        length += len(word) + 1
        if length >= chunk_size:
            chunks.append(" ".join(current).strip())
            current = []
            length = 0
    if current:
        chunks.append(" ".join(current).strip())
    return chunks


def _load_protocol_files() -> list[Path]:
    if not PROTOCOLS_DIR.exists():
        return []
    return [path for path in PROTOCOLS_DIR.rglob("*") if path.is_file() and path.suffix.lower() in _SUPPORTED_EXTENSIONS]


def retrieve_context_chunks(query: str, k: int = 3) -> list[dict]:
    query_terms = {term.lower() for term in query.split() if len(term) > 2}
    scored: list[tuple[int, dict]] = []

    for file_path in _load_protocol_files():
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for index, chunk in enumerate(_chunk_text(content)):
            lowered = chunk.lower()
            score = sum(1 for term in query_terms if term in lowered)
            if score == 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "source": file_path.name,
                        "page": index + 1,
                        "chunk": chunk,
                    },
                )
            )

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:k]]


def get_rag_context(query: str, k: int = 3) -> str:
    chunks = retrieve_context_chunks(query, k=k)
    return "\n\n---\n\n".join(
        f"[Source: {chunk['source']} | Page: {chunk['page']}]\n{chunk['chunk']}" for chunk in chunks
    )

