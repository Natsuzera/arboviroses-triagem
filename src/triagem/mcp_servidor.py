"""Ferramentas locais de organização do relato e consulta ao manifesto."""

import json
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

servidor = FastMCP("triagem-arboviroses")
MANIFESTO = Path(__file__).resolve().parents[2] / "documentos" / "fontes.json"
Relato = Literal["informado", "negado", "desconhecido"]


@servidor.tool()
def listar_fontes_oficiais(
    doenca: Literal["dengue", "chikungunya", "zika", "todas"] = "todas",
) -> list[dict]:
    """Lista referências do manifesto. Para zika, indica os manuais de dengue usados no diferencial."""
    fontes = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    filtro = "dengue" if doenca == "zika" else doenca
    return [
        {campo: fonte[campo] for campo in ("sigla", "titulo", "doenca", "url")}
        for fonte in fontes
        if filtro == "todas" or fonte["doenca"] == filtro
    ]


@servidor.tool()
def resumir_checklist_triagem(
    inicio_dos_sintomas: Relato = "desconhecido",
    idade: Literal["informado", "desconhecido"] = "desconhecido",
    gestacao: Relato = "desconhecido",
    comorbidades: Relato = "desconhecido",
    sangramento: Relato = "desconhecido",
    piora: Relato = "desconhecido",
) -> dict[str, list[str]]:
    """Agrupa fatos relatados por status. Use negado só quando a pessoa negar o item expressamente."""
    campos = {
        "inicio_dos_sintomas": inicio_dos_sintomas,
        "idade": idade,
        "gestacao": gestacao,
        "comorbidades": comorbidades,
        "sangramento": sangramento,
        "piora": piora,
    }
    grupos: dict[str, list[str]] = {"informado": [], "negado": [], "desconhecido": []}
    for campo, status in campos.items():
        grupos[status].append(campo)
    return grupos


if __name__ == "__main__":
    servidor.run(transport="stdio")
