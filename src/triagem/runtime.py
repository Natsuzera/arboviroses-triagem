"""Ciclo de vida do grafo integrado e registro de execução por turno."""

from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from triagem.grafo import build_graph
from triagem.mcp_cliente import carregar_ferramentas_mcp
from triagem.memoria import abrir_memoria
from triagem.skills_loader import CATALOGO, load_skill


@dataclass
class RegistroTurno:
    ferramentas: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    _skills_pendentes: dict[str, str] = field(default_factory=dict)

    def registrar(self, update: dict) -> None:
        for mensagem in (update or {}).get("messages", []):
            for chamada in getattr(mensagem, "tool_calls", []):
                self.ferramentas.append(chamada["name"])
                if chamada["name"] == "load_skill" and "nome" in chamada["args"]:
                    self._skills_pendentes[chamada["id"]] = chamada["args"]["nome"]
            if mensagem.type == "tool" and mensagem.name == "load_skill":
                nome = self._skills_pendentes.pop(mensagem.tool_call_id, None)
                if nome and mensagem.status == "success":
                    self.skills.append(nome)


@asynccontextmanager
async def abrir_grafo():
    mcp_tools = await carregar_ferramentas_mcp()
    async with abrir_memoria() as checkpointer:
        yield build_graph(
            extra_tools=[*mcp_tools, load_skill],
            system_extra=CATALOGO,
            checkpointer=checkpointer,
        )


async def executar_turno(
    graph,
    text: str,
    config: RunnableConfig,
    *,
    ao_atualizar: Callable[[str, dict], None] | None = None,
) -> tuple[str, RegistroTurno]:
    registro = RegistroTurno()
    async for step in graph.astream({"messages": [HumanMessage(text)]}, config, stream_mode="updates"):
        for node, update in step.items():
            registro.registrar(update)
            if ao_atualizar is not None:
                ao_atualizar(node, update or {})
    state = await graph.aget_state(config)
    return state.values["messages"][-1].text, registro
