#!/usr/bin/env python3
"""
One-time script to index protocol files into ChromaDB (or validate keyword index).

Usage:
    cd patient-followup-assistant
    python scripts/index_rag.py

What it does:
    1. Reads all .txt / .pdf files from data/protocols/
    2. Validates that retrieve_context_chunks() returns results for each diagnosis
    3. Prints a summary so you can confirm the RAG pipeline is working

No ChromaDB build step is needed — the RAG pipeline uses keyword scoring on raw files.
Run this once after cloning to confirm the protocols directory is set up correctly.
"""

import sys
import logging
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TEST_QUERIES = [
    "Cardiac — myocardial infarction",
    "Diabetes — Type 2",
    "Hypertension — hypertensive crisis",
    "Orthopaedic recovery",
    "general post-discharge",
]


def main() -> None:
    from src.config import PROTOCOLS_DIR
    from src.rag.pipeline import retrieve_context_chunks

    if not PROTOCOLS_DIR.exists():
        logger.error(f"Protocols directory not found: {PROTOCOLS_DIR}")
        logger.error("Copy your protocol files to data/protocols/ and retry.")
        sys.exit(1)

    files = list(PROTOCOLS_DIR.rglob("*"))
    supported = [f for f in files if f.is_file() and f.suffix.lower() in {".txt", ".md", ".pdf"}]

    if not supported:
        logger.error(f"No protocol files found in {PROTOCOLS_DIR}")
        logger.error("Add .txt, .md, or .pdf protocol files and retry.")
        sys.exit(1)

    logger.info(f"Found {len(supported)} protocol file(s): {[f.name for f in supported]}")
    logger.info("Running retrieval test for sample diagnoses...\n")

    all_ok = True
    for query in TEST_QUERIES:
        chunks = retrieve_context_chunks(query, k=3)
        if chunks:
            logger.info(f"[OK]  '{query}' → {len(chunks)} chunk(s) from {chunks[0]['source']}")
        else:
            logger.warning(f"[WARN] '{query}' → 0 chunks returned (no keyword match)")
            all_ok = False

    print()
    if all_ok:
        logger.info("RAG index validation passed. Protocol files are ready.")
    else:
        logger.warning("Some queries returned 0 chunks. Check protocol file content.")


if __name__ == "__main__":
    main()
