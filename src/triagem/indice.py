"""Índice dos manuais no Chroma."""

import argparse
import json
import re
import time

import pdfplumber
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from triagem.settings import COLLECTION, DOCS_DIR, EMBEDDINGS_TPM, INDEX_DIR, SOURCES_FILE, embeddings

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
BATCH = 20

BULLETS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9fࠀ-ࣿ-]")


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1


def clean(text: str) -> str:
    text = BULLETS.sub("•", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def load_pdf(source: dict) -> list[Document]:
    """Uma página por Document, numerada a partir de 1, sem o texto girado da lateral."""
    pages = []
    with pdfplumber.open(DOCS_DIR / source["arquivo"]) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            upright = page.filter(lambda obj: obj.get("object_type") != "char" or obj.get("upright", True))
            text = clean(upright.extract_text() or "")
            if len(text) < 200:
                continue
            metadata = {"sigla": source["sigla"], "titulo": source["titulo"], "doenca": source["doenca"], "fonte": source["url"], "page": number}
            pages.append(Document(text, metadata=metadata))
    return pages


def build_chunks() -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = []
    for source in json.loads(SOURCES_FILE.read_text()):
        pieces = splitter.split_documents(load_pdf(source))
        prefix = source["arquivo"].removesuffix(".pdf")
        counters: dict[int, int] = {}
        for piece in pieces:
            page = piece.metadata["page"]
            counters[page] = counters.get(page, 0) + 1
            piece.id = f"{prefix}-p{page}-{counters[page]}"
        chunks.extend(pieces)
        print(f"{source['sigla']:26s} {len(pieces):4d} trechos")
    return chunks


def open_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=embeddings(),
        persist_directory=str(INDEX_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )


def index(chunks: list[Document], store: Chroma | None = None) -> None:
    """Grava os trechos que faltam, em lotes espaçados pelo limite de tokens por minuto."""
    if store is None:
        store = open_store()
    done = set(store.get(include=[])["ids"])
    pending = [chunk for chunk in chunks if chunk.id not in done]
    print(f"já indexados: {len(done)} | faltam: {len(pending)}")

    for start in range(0, len(pending), BATCH):
        batch = pending[start:start + BATCH]
        tokens = sum(estimate_tokens(chunk.page_content) for chunk in batch)
        for attempt in range(3):
            try:
                store.add_documents(batch, ids=[chunk.id for chunk in batch])
                break
            except Exception as error:
                if "429" not in str(error) and "RESOURCE_EXHAUSTED" not in str(error):
                    raise
                if "PerDay" in str(error) or attempt == 2:
                    print(f"cota do embedding esgotada; {start} de {len(pending)} gravados. Rode de novo mais tarde.")
                    raise RuntimeError("Indexação incompleta. Execute uv run triagem quando a cota estiver disponível.") from None
                print("limite por minuto atingido, esperando 60 s")
                time.sleep(60)
        print(f"  {start + len(batch)}/{len(pending)} trechos (~{tokens} tokens)")
        time.sleep(60 * tokens / EMBEDDINGS_TPM)

    print("trechos no índice:", len(store.get(include=[])["ids"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--estimar", action="store_true", help="só conta os trechos e os tokens, sem chamar o embedding")
    args = parser.parse_args()

    chunks = build_chunks()
    tokens = sum(estimate_tokens(chunk.page_content) for chunk in chunks)
    print(f"total: {len(chunks)} trechos, ~{tokens} tokens, ~{tokens / EMBEDDINGS_TPM:.0f} min no limite de {EMBEDDINGS_TPM} tokens/min")
    if not args.estimar:
        index(chunks)
