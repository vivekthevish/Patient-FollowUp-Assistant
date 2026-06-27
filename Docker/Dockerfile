# ── Stage 1: build a self-contained venv ─────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# gcc needed to compile C extensions (e.g. chromadb, SQLAlchemy)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Create venv and install deps into it
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt


# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# curl is required by the API healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire venv — avoids --prefix issues with C-extension packages
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source and read-only data
COPY src/      ./src/
COPY data/     ./data/
COPY scripts/  ./scripts/

# data/db is mounted as a volume at runtime; pre-create so permissions are right
RUN mkdir -p data/db

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
date
EXPOSE 8000 8501
