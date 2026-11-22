"""Caminhos do projeto e modelos, lidos do .env na raiz."""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.rate_limiters import InMemoryRateLimiter

PROJECT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_DIR / "documentos"
SOURCES_FILE = DOCS_DIR / "fontes.json"
INDEX_DIR = PROJECT_DIR / "chroma_arboviroses"
COLLECTION = "arboviroses"

load_dotenv(PROJECT_DIR / ".env")

MODEL = os.getenv("MODEL", "google_genai:gemini-3.5-flash-lite")
EMBEDDINGS = os.getenv("EMBEDDINGS", "google_genai:gemini-embedding-2")

MODEL_RPM = int(os.getenv("MODEL_RPM", "12"))
EMBEDDINGS_TPM = int(os.getenv("EMBEDDINGS_TPM", "25000"))

_rate_limiter = InMemoryRateLimiter(requests_per_second=MODEL_RPM / 60, check_every_n_seconds=0.5, max_bucket_size=1)


def chat_model(temperature: float = 0.0):
    return init_chat_model(MODEL, temperature=temperature, rate_limiter=_rate_limiter)


def embeddings():
    return init_embeddings(EMBEDDINGS)
