"""Interface de triagem de arboviroses."""

import asyncio
from base64 import b64encode
from pathlib import Path

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


def confirmar_exclusao(identificador, titulo):
    st.write("**Excluir esta conversa?**")
    st.text(titulo)
    st.write("As mensagens e a memória desta conversa serão apagadas permanentemente.")
    cancelar, confirmar = st.columns(2)
    if cancelar.button("Cancelar", use_container_width=True):
        st.session_state.pop("exclusao", None)
        st.rerun()
    if confirmar.button("Excluir", type="primary", use_container_width=True):
        historico.excluir(identificador)
        st.session_state.pop("exclusao", None)
        st.session_state.config = configurar_conversa()
        st.rerun()


assets = Path(__file__).parent / "assets"
icone = assets / "simbolo.png"
st.set_page_config(page_title="Arbo · Triagem", page_icon=str(icone))
st.html("<style>" + (assets / "interface.css").read_text() + "</style>")
simbolo = b64encode(icone.read_bytes()).decode()
st.sidebar.markdown(
    f'<div class="identidade"><img alt="" src="data:image/png;base64,{simbolo}">Arbo</div>',
    unsafe_allow_html=True,
)
conversas = historico.listar()
if st.sidebar.button("Nova conversa", icon=":material/add:", use_container_width=True) or "config" not in st.session_state:
    st.session_state.config = configurar_conversa()
    st.session_state.pop("exclusao", None)

if conversas:
    st.sidebar.subheader("Histórico")
for identificador, titulo in conversas:
    ativa = identificador == st.session_state.config["configurable"]["thread_id"]
    if st.sidebar.button(titulo, key=identificador, use_container_width=True, type="primary" if ativa else "secondary"):
        st.session_state.config = configurar_conversa(identificador)
        if not ativa:
            st.session_state.pop("exclusao", None)
            st.rerun()

thread_id = st.session_state.config["configurable"]["thread_id"]
mensagens = historico.mensagens(thread_id)
sugestao = None
if mensagens:
    if st.sidebar.button("Excluir conversa", icon=":material/delete_outline:"):
        st.session_state.exclusao = thread_id
    if st.session_state.get("exclusao") == thread_id:
        with st.sidebar.container(border=True):
            confirmar_exclusao(thread_id, dict(conversas).get(thread_id, "Conversa"))
    st.html('<header class="cabecalho compacto"><h1>Triagem de arboviroses</h1></header>')
else:
    st.html('<header class="cabecalho"><h1>Triagem de arboviroses</h1>'
            '<p>Descreva o que está sentindo ou tire uma dúvida sobre dengue, chikungunya e zika.</p></header>')
    st.subheader("Por onde começar?")
    opcoes = [
        ("Relatar sintomas", ":material/stethoscope:", "Quero relatar meus sintomas. Por onde começo?"),
        ("Comparar doenças", ":material/compare_arrows:", "Quais as diferenças entre dengue, chikungunya e zika?"),
        ("Consultar manuais", ":material/menu_book:", "Quais são os manuais usados na triagem?"),
    ]
    for coluna, (rotulo, icone_botao, pergunta) in zip(st.columns(3), opcoes):
        if coluna.button(rotulo, icon=icone_botao, use_container_width=True):
            sugestao = pergunta

for mensagem in mensagens:
    mostrar(mensagem)

texto = st.chat_input("Escreva sua mensagem", max_chars=MAX_CHARS) or sugestao
if texto:
    pergunta = {"role": "user", "texto": texto}
    mostrar(pergunta)
    with FileLock(historico.arquivo(thread_id).with_suffix(".lock")):
        turno = historico.mensagens(thread_id)
        if mensagens and not turno:
            st.session_state.config = configurar_conversa()
            st.rerun()
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
