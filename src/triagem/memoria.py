"""Configuração da persistência local das conversas."""

from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from triagem.settings import PROJECT_DIR


def abrir_memoria():
    return AsyncSqliteSaver.from_conn_string(str(PROJECT_DIR / "checkpoints.db"))


def configurar_conversa(thread_id: str | None = None) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id or str(uuid4())}}
