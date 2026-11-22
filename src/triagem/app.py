"""Entrada do aplicativo: prepara a base local e inicia a interface."""

import hashlib
import json
import os
import subprocess
import sys

from filelock import FileLock

from triagem.indice import build_chunks, index, open_store
from triagem.settings import DOCS_DIR, INDEX_DIR, PROJECT_DIR, SOURCES_FILE


def preparar_base() -> None:
    manifesto = SOURCES_FILE.read_bytes()
    pdfs = [DOCS_DIR / fonte["arquivo"] for fonte in json.loads(manifesto)]
    if not pdfs:
        raise RuntimeError("O manifesto dos manuais está vazio.")
    if any(not pdf.is_file() for pdf in pdfs):
        subprocess.run([sys.executable, str(PROJECT_DIR / "coletor/agente.py")], check=True)
        if any(not pdf.is_file() for pdf in pdfs):
            raise RuntimeError("Falha no download dos manuais. Execute uv run triagem para tentar novamente.")

    store = open_store()
    assinatura = hashlib.sha256(manifesto).hexdigest()
    marcador = INDEX_DIR / "base-pronta.json"
    if marcador.is_file():
        try:
            anterior = json.loads(marcador.read_text())
        except ValueError:
            anterior = {}
        if anterior.get("manifesto") == assinatura:
            existentes = set(store.get(include=[])["ids"])
            if anterior.get("ids") and existentes.issuperset(anterior["ids"]):
                return

    print("Verificando os trechos dos manuais para completar o índice…", flush=True)
    trechos = build_chunks()
    if not trechos:
        raise RuntimeError("Nenhum trecho foi extraído dos manuais.")
    index(trechos, store)
    temporario = marcador.with_suffix(".tmp")
    temporario.write_text(json.dumps({"manifesto": assinatura, "ids": [t.id for t in trechos]}))
    temporario.replace(marcador)


def main() -> None:
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("Preencha GOOGLE_API_KEY no .env da raiz. Use .env.example como modelo.")
    INDEX_DIR.mkdir(exist_ok=True)
    with FileLock(INDEX_DIR / "preparacao.lock"):
        preparar_base()
    os.execv(sys.executable, [sys.executable, "-m", "streamlit", "run", str(PROJECT_DIR / "streamlit_app.py"), "--server.address=localhost", *sys.argv[1:]])
