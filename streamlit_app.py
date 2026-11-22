"""Interface de triagem de arboviroses."""

import asyncio

import streamlit as st
from filelock import FileLock

from triagem import historico
from triagem.guardrails import MAX_CHARS, screen_input
from triagem.memoria import configurar_conversa
from triagem.runtime import abrir_grafo, executar_turno


async def responder(texto, config):
    async with abrir_grafo() as grafo:
        return await executar_turno(grafo, texto, config)


def mostrar(mensagem):
    with st.chat_message(mensagem["role"]):
        st.text(mensagem["texto"])
        if mensagem.get("ferramentas"):
            with st.expander("Como a resposta foi elaborada"):
                st.write("Ferramentas usadas", mensagem["ferramentas"])
                if mensagem["skills"]:
                    st.write("Skills consultadas", mensagem["skills"])


st.set_page_config(page_title="Triagem de arboviroses", page_icon="🩺")
st.title("Triagem de arboviroses")
st.write("Descreva seus sintomas ou tire uma dúvida sobre dengue, chikungunya ou zika.")
conversas = historico.listar()
if st.sidebar.button("Nova conversa") or "config" not in st.session_state:
    st.session_state.config = configurar_conversa()

if conversas:
    st.sidebar.subheader("Conversas")
for identificador, titulo in conversas:
    ativa = identificador == st.session_state.config["configurable"]["thread_id"]
    if st.sidebar.button(titulo, key=identificador, type="primary" if ativa else "secondary"):
        st.session_state.config = configurar_conversa(identificador)
        if not ativa:
            st.rerun()

thread_id = st.session_state.config["configurable"]["thread_id"]
for mensagem in historico.mensagens(thread_id):
    mostrar(mensagem)

if texto := st.chat_input("Escreva sua mensagem", max_chars=MAX_CHARS):
    pergunta = {"role": "user", "texto": texto}
    mostrar(pergunta)
    with FileLock(historico.arquivo(thread_id).with_suffix(".lock")):
        turno = historico.mensagens(thread_id)
        turno.append(pergunta)
        historico.salvar(thread_id, turno)
        try:
            with st.spinner("Analisando seu relato…"):
                resposta, registro = asyncio.run(responder(texto, st.session_state.config))
            mensagem = {"role": "assistant", "texto": resposta,
                        "ferramentas": registro.ferramentas, "skills": registro.skills}
        except Exception:
            fallback = screen_input(texto)
            mensagem = {"role": "assistant", "texto": fallback or
                        "A triagem está indisponível. Confira a configuração da chave, a conexão e o índice dos manuais. "
                        "Em caso de urgência, procure atendimento imediatamente."}
        turno.append(mensagem)
        historico.salvar(thread_id, turno)
    st.rerun()
