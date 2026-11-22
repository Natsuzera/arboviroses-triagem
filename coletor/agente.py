"""Baixa os manuais do Ministério da Saúde usados na base."""

import argparse
import json
import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.tools import tool

from triagem.settings import DOCS_DIR, SOURCES_FILE, chat_model

USER_AGENT = "Mozilla/5.0 (triagem-arboviroses)"

START_PAGES = [
    "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/d/dengue",
    "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/c/chikungunya",
    "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/z/zika-virus",
]

TASK = """Encontre e baixe os documentos oficiais do Ministério da Saúde que orientam a triagem e o manejo clínico de pacientes com suspeita de arbovirose:

1. Dengue: diagnóstico e manejo clínico – adulto e criança (a edição mais recente).
2. Chikungunya: manejo clínico (a edição mais recente).
3. Dengue: manual de enfermagem (traz o acolhimento com classificação de risco).
4. Um documento do Ministério sobre a abordagem clínica da zika, se houver um PDF oficial.

Comece por estas páginas:
{pages}

Os itens das páginas de publicações costumam redirecionar direto para o PDF: abra o item com listar_links e, se ele disser que a URL já é um PDF, baixe pela URL final.
Para cada documento: baixe o PDF com baixar_pdf e, se o download der certo, registre uma única vez com registrar_fonte, com o ano que aparece no título ou na URL.
Não tente adivinhar URLs; use só links que alguma ferramenta mostrou.
Prefira a versão publicada pelo próprio Ministério (gov.br/saude ou bvsms.saude.gov.br) a cópias de estados ou municípios.
Não baixe cartazes, folders, notas técnicas de uma página nem boletins epidemiológicos.
No fim, liste o que foi baixado e o que não foi encontrado."""


def allowed(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host == "gov.br" or host.endswith(".gov.br")


def download(url: str, timeout: int = 120) -> tuple[bytes, str]:
    """Faz o GET e devolve o conteúdo e a URL final, depois dos redirecionamentos."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), response.url


def load_sources() -> list[dict]:
    return json.loads(SOURCES_FILE.read_text()) if SOURCES_FILE.exists() else []


def save_pdf(url: str, file: str) -> str:
    if not allowed(url):
        return f"recusado: {url} não é um domínio gov.br"
    path = DOCS_DIR / Path(file).name
    if path.exists():
        return f"já existe: {path.name}"
    content, _ = download(url)
    if not content.startswith(b"%PDF"):
        return f"erro: {url} não devolveu um PDF"
    with NamedTemporaryFile(dir=DOCS_DIR, delete=False) as temp:
        temp.write(content)
    Path(temp.name).replace(path)
    return f"baixado: {path.name} ({len(content) // 1024} KB)"


@tool
def listar_links(url: str, apenas_pdf: bool = False) -> str:
    """Abre uma página e lista os links do conteúdo dela, um por linha, com o texto do link. Com apenas_pdf, só os links para PDF."""
    if not allowed(url):
        return f"recusado: {url} não é um domínio gov.br"
    content, final_url = download(url, timeout=60)
    if content.startswith(b"%PDF"):
        return f"esta URL já é um PDF ({len(content) // 1024} KB); baixe com baixar_pdf usando a URL final {final_url}"
    if not allowed(final_url):
        return f"a página redireciona para {final_url}, fora do gov.br"
    soup = BeautifulSoup(content, "html.parser")
    content = soup.select_one("#content") or soup
    lines = []
    for anchor in content.find_all("a", href=True):
        href = urljoin(final_url, anchor["href"]).split("#")[0]
        text = " ".join(anchor.get_text(" ").split())
        if not text or not allowed(href) or (apenas_pdf and ".pdf" not in href.lower()):
            continue
        lines.append(f"{text} -> {href}")
    return "\n".join(list(dict.fromkeys(lines))[:60]) or "nenhum link encontrado"


@tool
def baixar_pdf(url: str, arquivo: str) -> str:
    """Baixa um PDF de um domínio gov.br e grava em documentos/ com o nome de arquivo dado, como dengue_manejo_2024.pdf."""
    try:
        return save_pdf(url, arquivo)
    except Exception as error:
        return f"erro ao baixar {url}: {error}"


@tool
def registrar_fonte(sigla: str, titulo: str, doenca: str, ano: int, url: str, arquivo: str) -> str:
    """Registra um documento baixado no documentos/fontes.json.

    sigla: nome curto usado na citação, como "Dengue MS 2024".
    doenca: dengue, chikungunya, zika ou arboviroses.
    """
    if not (DOCS_DIR / arquivo).exists():
        return f"erro: {arquivo} não está em documentos/; baixe antes de registrar"
    sources = [s for s in load_sources() if s["arquivo"] != arquivo and s["url"] != url]
    sources.append({"sigla": sigla, "titulo": titulo, "doenca": doenca, "ano": ano, "orgao": "Ministério da Saúde", "url": url, "arquivo": arquivo})
    SOURCES_FILE.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n")
    return f"registrado: {sigla}"


def from_manifest() -> None:
    for source in load_sources():
        print(f"{source['sigla']:22s}", save_pdf(source["url"], source["arquivo"]))


def run_agent() -> None:
    agent = create_agent(chat_model(), tools=[listar_links, baixar_pdf, registrar_fonte])
    task = TASK.format(pages="\n".join(f"- {page}" for page in START_PAGES))
    for step in agent.stream({"messages": [HumanMessage(task)]}, {"recursion_limit": 40}, stream_mode="updates"):
        for message in next(iter(step.values()))["messages"]:
            if message.type == "tool":
                print(f"  {message.name}: {message.content[:120]!r}")
            elif message.tool_calls:
                for call in message.tool_calls:
                    print("chamada:", call["name"], call["args"])
            else:
                print(message.text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agente", action="store_true", help="procura os documentos com o agente em vez de ler o manifesto")
    DOCS_DIR.mkdir(exist_ok=True)
    if parser.parse_args().agente:
        run_agent()
    else:
        from_manifest()
