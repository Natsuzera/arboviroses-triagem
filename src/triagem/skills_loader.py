"""Catálogo leve e leitura sob demanda das skills empacotadas."""

from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

SkillName = Literal["triagem-inicial", "reavaliacao"]
SKILLS_DIR = Path(__file__).resolve().parent / "skills"
CATALOGO = """# Catálogo de skills
- triagem-inicial: primeiro relato de sintomas ou início de uma nova avaliação.
- reavaliacao: novo sintoma, mudança do quadro ou dúvida sobre orientação anterior na mesma conversa.

Quando houver uma skill aplicável, chame load_skill com seu nome. Faça essa chamada sozinha,
antes de buscar nos manuais. Aplique os passos da skill, consulte as ferramentas auxiliares
necessárias e só depois chame search_protocolos em uma chamada separada. Ao formular a
consulta, inclua os fatos relevantes que a skill ajudou a organizar. Carregue a skill uma
vez por turno. Cumprimentos e dúvidas gerais sem relato não precisam de skill.
"""


@tool
def load_skill(nome: SkillName) -> str:
    """Carrega as instruções completas da skill selecionada no catálogo."""
    if nome not in ("triagem-inicial", "reavaliacao"):
        raise ValueError("Skill fora do catálogo")
    return (SKILLS_DIR / nome / "SKILL.md").read_text(encoding="utf-8")
