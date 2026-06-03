import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "careconnect-documents")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PERSIST_DIR = os.path.join(BASE_DIR, "chroma_db")
DOCUMENTS_DIR = os.path.join(BASE_DIR, "..", "Synthetic_Documents")
DATASET_DIR = os.path.join(BASE_DIR, "..", "Dataset")

MODEL_NAME = "gpt-4o"
EMBEDDING_MODEL = "text-embedding-3-small"
MAX_RETRIES = 3
RETRY_DELAY = 2
TEMPERATURE = 0.3
