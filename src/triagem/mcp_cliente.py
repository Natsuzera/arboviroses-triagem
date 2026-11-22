"""Descoberta das ferramentas dos dois servidores MCP."""

import sys

from langchain_core.tools import BaseTool, tool
from langchain_mcp_adapters.client import MultiServerMCPClient

FUSO_DEMONSTRACAO = "America/Sao_Paulo"


async def carregar_ferramentas_mcp() -> list[BaseTool]:
    cliente = MultiServerMCPClient({
        "triagem": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "triagem.mcp_servidor"],
        },
        "relogio": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "mcp_server_time", "--local-timezone", FUSO_DEMONSTRACAO],
        },
    })
    ferramentas = {ferramenta.name: ferramenta for ferramenta in await cliente.get_tools()}
    esperadas = {"listar_fontes_oficiais", "resumir_checklist_triagem", "get_current_time"}
    if ausentes := esperadas - ferramentas.keys():
        raise RuntimeError(f"Ferramentas MCP ausentes: {', '.join(sorted(ausentes))}")

    @tool
    async def get_current_time() -> str | list:
        """Consulta a data e hora civil para interpretar datas relativas na sessão de demonstração."""
        try:
            return await ferramentas["get_current_time"].ainvoke({"timezone": FUSO_DEMONSTRACAO})
        except Exception:
            return "Relógio indisponível. Se a data for relevante, pergunte à pessoa."

    return [ferramentas["listar_fontes_oficiais"], ferramentas["resumir_checklist_triagem"], get_current_time]
