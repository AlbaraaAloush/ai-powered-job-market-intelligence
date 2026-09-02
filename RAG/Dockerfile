# Backend image — FastAPI + RAG pipeline.
#
# Build from the RAG/ directory:  docker build -t gcc-jobs-api ./RAG
#
# Notes:
#  - INSTALL_RAG_MODELS=false builds a much smaller image for the dashboard and
#    SQL/Pandas chat fallback. The full image installs CPU-only torch and bakes
#    the embedding model for deterministic semantic-RAG cold starts.
#  - Secrets are NOT baked — pass them at runtime via env_file/environment.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

ARG INSTALL_RAG_MODELS=true

COPY requirements-api.txt requirements-rag.txt ./
RUN pip install -r requirements-api.txt \
 && if [ "$INSTALL_RAG_MODELS" = "true" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu \
      && pip install -r requirements-rag.txt; \
    fi

# Non-root user before model download so the cache lands in its home dir.
RUN useradd --create-home appuser
USER appuser

# Bake the embedding model only in the full semantic-RAG image.
RUN if [ "$INSTALL_RAG_MODELS" = "true" ]; then \
      python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"; \
    fi

# App code last — changes here don't invalidate the heavy layers above.
COPY --chown=appuser:appuser . .

EXPOSE 8000

# Startup loads ~30k rows + the embedding model: give the healthcheck a
# generous start period before it begins counting failures.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)"

# --no-server-header: see SECURITY.md (can't be stripped at app level)
# --proxy-headers: trust X-Forwarded-* from the nginx container in front
CMD ["python", "-m", "uvicorn", "server:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--no-server-header", "--proxy-headers"]
