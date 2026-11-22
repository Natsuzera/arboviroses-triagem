"""Busca nos manuais, avaliação dos trechos e reescrita da consulta."""

from functools import cache
from typing import Literal

from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from triagem.settings import COLLECTION, INDEX_DIR, chat_model, embeddings

K = 5


@cache
def vector_store() -> Chroma:
    if not INDEX_DIR.exists():
        raise RuntimeError("índice não encontrado; rode python -m triagem.indice")
    return Chroma(collection_name=COLLECTION, embedding_function=embeddings(), persist_directory=str(INDEX_DIR))


def format_docs(documents: list[Document]) -> str:
    return "\n\n".join(f"[{doc.metadata['sigla']}, p. {doc.metadata['page']}] {doc.page_content}" for doc in documents)


@tool
def search_protocolos(query: str, doenca: Literal["dengue", "chikungunya", "todas"] = "todas") -> str:
    """Busca trechos dos manuais do Ministério da Saúde sobre dengue e chikungunya: sinais e sintomas, sinais de alarme,
    classificação de risco (grupos A, B, C e D), exames, hidratação, tratamento e diagnóstico diferencial com zika.

    query: o que procurar, nos termos de um manual clínico.
    doenca: restringe a busca aos manuais de uma doença; use "todas" quando a doença ainda não está clara.
    """
    search_filter = None if doenca == "todas" else {"doenca": doenca}
    documents = vector_store().max_marginal_relevance_search(query, k=K, fetch_k=20, lambda_mult=0.7, filter=search_filter)
    return format_docs(documents)


GRADE_PROMPT = """# Papel
Você avalia se trechos recuperados de manuais clínicos servem para responder a uma mensagem.

# Regras
Responda 'sim' só se algum trecho traz a informação que a mensagem pede, mesmo com outras palavras.
Quando a mensagem descreve sintomas, basta que os trechos tragam os critérios de classificação ou a conduta que se aplicam ao quadro; não se exige um diagnóstico.
Responda 'nao' se os trechos só compartilham palavras ou o tema geral com a mensagem.
A consulta mostra o que o assistente procurou; use-a para entender mensagens curtas que dependem da conversa.

# Mensagem do usuário
<mensagem>
{question}
</mensagem>

# Consulta feita
<consulta>
{query}
</consulta>

# Trechos
<trechos>
{context}
</trechos>"""


class GradeDocuments(BaseModel):
    """Veredito sobre a relevância dos trechos."""

    reason: str = Field(description="uma frase dizendo o que os trechos trazem ou o que falta neles")
    binary_score: Literal["sim", "nao"] = Field(description="'sim' se os trechos respondem à mensagem, 'nao' se não")


REWRITE_PROMPT = """# Papel
Você reescreve consultas para a busca em manuais do Ministério da Saúde sobre dengue e chikungunya.

# Regras
Troque as expressões do dia a dia pelos termos clínicos que o manual usaria, como "sangue na gengiva" por "sangramento de mucosas" ou "manchas vermelhas" por "exantema".
Mantenha os dados do paciente que mudam a conduta, como idade, gestação e doenças crônicas.
A primeira busca não trouxe o que precisava; o motivo está na avaliação. Procure por outro ângulo.
Responda só com a consulta reescrita.

# Mensagem do usuário
<mensagem>
{question}
</mensagem>

# Consulta anterior
<consulta>
{query}
</consulta>

# Avaliação
<avaliacao>
{reason}
</avaliacao>"""


@cache
def grader():
    return chat_model().with_structured_output(GradeDocuments)


def grade(question: str, query: str, context: str) -> GradeDocuments:
    return grader().invoke(GRADE_PROMPT.format(question=question, query=query, context=context))


def rewrite(question: str, query: str, reason: str) -> str:
    return chat_model().invoke(REWRITE_PROMPT.format(question=question, query=query, reason=reason)).text.strip()
