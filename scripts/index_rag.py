#!/usr/bin/env python3
"""
Script to index protocol files into ChromaDB vector database.

Usage:
    cd patient-followup-assistant
    python scripts/index_rag.py

What it does:
    1. Reads all .txt / .pdf files from data/protocols/
    2. Chunks the content with overlap
    3. Generates embeddings using Google Generative AI
    4. Stores vectors in ChromaDB for semantic search
    5. Validates retrieval with test queries

Run this script:
    - After cloning the repository (first time setup)
    - When adding new protocol files
    - To rebuild the index (use --reset flag)
"""

import sys
import logging
import argparse
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
    parser = argparse.ArgumentParser(description="Index protocol files into ChromaDB")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the vectorstore before indexing (deletes all existing data)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation queries after indexing",
    )
    args = parser.parse_args()

    try:
        from src.config import PROTOCOLS_DIR, CHROMA_PERSIST_DIR, GEMINI_API_KEY
        from src.rag.pipeline import index_protocols, reset_vectorstore, retrieve_context_chunks

        # Check API key
        if not GEMINI_API_KEY:
            logger.error("GOOGLE_API_KEY or GEMINI_API_KEY must be set in .env file")
            logger.error("Copy .env.template to .env and add your API key")
            sys.exit(1)

        # Check protocols directory
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
        
        # Reset if requested
        if args.reset:
            logger.info("Resetting vectorstore...")
            reset_vectorstore()
            logger.info("Vectorstore reset complete")

        # Index protocols
        logger.info("Starting indexing process...")
        logger.info(f"ChromaDB will be stored at: {CHROMA_PERSIST_DIR}")
        
        num_chunks = index_protocols()
        
        if num_chunks == 0:
            logger.info("No new documents to index (all already present)")
            logger.info("Use --reset flag to rebuild the entire index")
        else:
            logger.info(f"Successfully indexed {num_chunks} chunks")

        # Validation
        if not args.skip_validation:
            logger.info("\nRunning retrieval validation with test queries...\n")
            
            all_ok = True
            for query in TEST_QUERIES:
                try:
                    chunks = retrieve_context_chunks(query, k=3)
                    if chunks:
                        sources = {chunk['source'] for chunk in chunks}
                        logger.info(f"[OK]  '{query}' → {len(chunks)} chunk(s) from {', '.join(sources)}")
                    else:
                        logger.warning(f"[WARN] '{query}' → 0 chunks returned")
                        all_ok = False
                except Exception as exc:
                    logger.error(f"[ERROR] '{query}' → {exc}")
                    all_ok = False

            print()
            if all_ok:
                logger.info("✓ ChromaDB index validation passed. RAG pipeline is ready.")
            else:
                logger.warning("⚠ Some queries returned 0 chunks. Check protocol file content.")
        
        logger.info("\nIndexing complete!")
        logger.info(f"ChromaDB data stored at: {CHROMA_PERSIST_DIR}")
        logger.info("You can now run the application with: python -m src.api.main")

    except ImportError as exc:
        logger.error(f"Import error: {exc}")
        logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Indexing failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

 
