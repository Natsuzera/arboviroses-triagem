"""Histórico local de conversas."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from filelock import FileLock
from langgraph.checkpoint.sqlite import SqliteSaver

from triagem.settings import PROJECT_DIR

PASTA = PROJECT_DIR / "conversas"


def arquivo(thread_id: str) -> Path:
    return PASTA / f"{UUID(thread_id)}.json"


def mensagens(thread_id: str) -> list[dict]:
    caminho = arquivo(thread_id)
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else []


def salvar(thread_id: str, historico: list[dict]) -> None:
    """Salva as mensagens da conversa em JSON."""
    caminho = arquivo(thread_id)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def importar_anteriores() -> None:
    banco = PROJECT_DIR / "checkpoints.db"
    if not banco.is_file():
        return
    with closing(sqlite3.connect(banco)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='checkpoints'").fetchone():
            return
        saver = SqliteSaver(conn)
        for (thread_id,) in conn.execute("SELECT DISTINCT thread_id FROM checkpoints WHERE checkpoint_ns=''"):
            try:
                caminho = arquivo(thread_id)
            except ValueError:
                continue
            if caminho.exists():
                continue
            with FileLock(caminho.with_suffix(".lock")):
                if caminho.exists():
                    continue
                checkpoint = saver.get_tuple({"configurable": {"thread_id": thread_id}})
                historico = []
                if checkpoint:
                    for m in checkpoint.checkpoint["channel_values"].get("messages", []):
                        if m.type == "human":
                            historico.append({"role": "user", "texto": m.text})
                        elif m.type == "ai" and not m.tool_calls and m.text:
                            historico.append({"role": "assistant", "texto": m.text})
                if historico:
                    salvar(thread_id, historico)


def listar() -> list[tuple[str, str]]:
    PASTA.mkdir(exist_ok=True)
    importar_anteriores()
    itens = []
    for caminho in sorted(PASTA.glob("*.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True):
        titulo = next((m["texto"] for m in mensagens(caminho.stem) if m["role"] == "user"), "")
        itens.append((caminho.stem, " ".join(titulo.split())[:60] or "Conversa"))
    return itens
