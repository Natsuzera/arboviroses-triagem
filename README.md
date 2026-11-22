# Triagem de arboviroses

Assistente de triagem para pacientes com suspeita de dengue, chikungunya ou zika, construído como um grafo do LangGraph com RAG agêntico sobre os manuais do Ministério da Saúde.

**Participantes:** Daniel Moura e Ewerton

> Esta versão cobre grafo, RAG agêntico, MCP, skills e memória persistente. O terminal e a interface Streamlit usam os mesmos guardrails de entrada e saída.

## O que o assistente faz e para quem

A pessoa descreve o que está sentindo, e o assistente cruza o relato com os critérios dos manuais do Ministério da Saúde. Quando há suspeita de dengue e dados suficientes, a resposta pode sugerir um grupo de risco provisório (A, B, C ou D), quais sinais de alarme apareceram ou ainda faltam informar e o que o manual manda fazer, sempre com o documento e a página. Quando falta um dado que muda a classificação, como idade, gestação ou doença crônica, o assistente pergunta antes. Ele também responde dúvidas sobre as doenças, como a diferença entre a dor articular da dengue e a da chikungunya.

O público é quem está na fila de uma unidade de saúde ou em casa tentando decidir se precisa de atendimento. O assistente não substitui a avaliação profissional.

### Por que arboviroses

O tema da dupla é triagem de pacientes. Triagem em saúde no geral exigiria dezenas de protocolos, um para cada queixa. As arboviroses têm um protocolo de triagem próprio e bem definido: o manual de dengue do Ministério classifica o paciente em quatro grupos por sinais de alarme, comorbidades e sinais de choque, e cada grupo tem uma conduta. São doenças comuns no Brasil, com epidemias todo ano, e três documentos oficiais cobrem o assunto.

Os PCDTs do gov.br foram considerados, mas são protocolos de tratamento (que medicamento o SUS fornece e para quem), não de triagem, e nenhum trata de dengue.

## Documentos

| Sigla | Documento | Páginas | Origem |
|---|---|---|---|
| Dengue MS 2024 | *Dengue: diagnóstico e manejo clínico – adulto e criança*, 6ª edição | 83 | [gov.br/saude](https://www.gov.br/saude/pt-br/centrais-de-conteudo/publicacoes/svsa/dengue/dengue-diagnostico-e-manejo-clinico-adulto-e-crianca) |
| Dengue Enfermagem MS 2026 | *Dengue: manual de enfermagem*, 3ª edição revisada | 110 | [bvsms.saude.gov.br](https://bvsms.saude.gov.br/bvs/publicacoes/dengue_manual_enfermagem_3ed_rev.pdf) |
| Chikungunya MS 2025 | *Chikungunya: manejo clínico*, 2ª edição revisada | 74 | [gov.br/saude](https://www.gov.br/saude/pt-br/centrais-de-conteudo/publicacoes/guias-e-manuais/2025/chikungunya-manejo-clinico-2o-edicao-revisada.pdf/@@download/file) |

Todos são publicações do Ministério da Saúde sob licença Creative Commons. O manual de dengue é o núcleo da triagem, com o fluxograma e os grupos A a D. O de enfermagem traz o acolhimento com classificação de risco, que é a etapa da triagem feita na recepção da unidade. O de chikungunya cobre as fases da doença e o diagnóstico diferencial. O Ministério não tem um manual clínico próprio para zika; o diagnóstico diferencial com zika está no manual de dengue.

Os PDFs não ficam no repositório. O `documentos/fontes.json` registra título, ano, URL e arquivo de cada um, e o coletor baixa tudo a partir dele.

### Coletor

O `coletor/agente.py` tem dois modos:

- **padrão**: lê o `fontes.json` e baixa o que falta, sem chamar o modelo. É o modo para reproduzir a base.
- **`--agente`**: um agente com três ferramentas (`listar_links`, `baixar_pdf`, `registrar_fonte`) parte das páginas de dengue, chikungunya e zika no gov.br, encontra os manuais e preenche o `fontes.json`. Ele só aceita domínios `gov.br` e confere se o arquivo baixado é mesmo um PDF. Foi com ele que a base foi montada, e é com ele que se troca ou se acrescenta um documento.

A ferramenta `listar_links` só lê o bloco de conteúdo das páginas do gov.br. Na primeira versão ela devolvia os cerca de 250 links de menu e rodapé de cada página, uns 7 mil tokens por chamada, e o agente estourou o limite de tokens por minuto do plano gratuito em poucos passos.

## Indexação

`python -m triagem.indice` lê os PDFs com o `pdfplumber`, corta em trechos e grava no Chroma, em `chroma_arboviroses/`.

- **Texto girado.** Os manuais repetem o título e o "Brasília – DF" em uma faixa vertical na lateral da página, que o extrator intercalava com o conteúdo, de trás para frente ("ailísarB"). O loader descarta os caracteres que não estão na vertical antes de extrair o texto.
- **Marcadores.** Os marcadores de lista vêm de fontes de símbolos e saíam como caracteres de controle; viram "•". Palavras hifenizadas na quebra de linha são juntadas.
- **Páginas.** Uma página por `Document`, contada a partir de 1, como no leitor de PDF. A página citada na resposta é a do arquivo, que pode diferir em um ou dois do número impresso no rodapé.
- **Trechos.** `RecursiveCharacterTextSplitter` com 1200 caracteres e 150 de sobreposição. O manual de dengue descreve cada grupo de risco, com caracterização e conduta, em cerca de mil caracteres, e com 1200 o grupo inteiro cabe em um trecho. São 490 trechos no total.
- **Metadados.** `sigla`, `titulo`, `doenca`, `fonte` (URL) e `page`. O `doenca` permite filtrar a busca por manual.
- **Retomável.** Os ids são estáveis (`arquivo-p{página}-{n}`), e o script pula o que já está no índice. Os lotes são espaçados para caber no limite de tokens por minuto do embedding. `--estimar` mostra quantos trechos e tokens a indexação vai gastar antes de gastar.

## Grafo

```mermaid
graph TD;
	__start__([__start__]):::first
	start_turn(start_turn)
	generate_query_or_respond(generate_query_or_respond)
	retrieve(retrieve)
	grade_documents(grade_documents)
	rewrite_question(rewrite_question)
	generate_answer(generate_answer)
	__end__([__end__]):::last
	__start__ --> start_turn;
	start_turn -. entrada aceita .-> generate_query_or_respond;
	start_turn -. entrada filtrada .-> __end__;
	generate_query_or_respond -.-> __end__;
	generate_query_or_respond -. tools .-> retrieve;
	retrieve -.-> grade_documents;
	retrieve -.-> generate_query_or_respond;
	grade_documents -.-> generate_answer;
	grade_documents -.-> rewrite_question;
	rewrite_question --> retrieve;
	generate_answer --> __end__;
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

Os filtros de saída são aplicados antes de gravar a mensagem final no estado.

| Nó | Função |
|---|---|
| `start_turn` | grava a mensagem do usuário em `question` e zera `rewrites` e `grade`. Não chama o modelo |
| `generate_query_or_respond` | o modelo, com as ferramentas ligadas, decide se busca nos manuais e escreve a consulta em termos clínicos, com os dados do paciente que já apareceram na conversa. A cumprimentos responde direto |
| `retrieve` | `ToolNode` que executa as ferramentas pedidas |
| `grade_documents` | o modelo julga, em saída estruturada, se os trechos respondem à mensagem, com uma frase de justificativa. Aprovados, segue para a resposta; reprovados, para a reescrita; esgotado o limite, para a resposta, que vai dizer que não encontrou |
| `rewrite_question` | reescreve a consulta no vocabulário do manual, usando a justificativa da avaliação, e já pede a nova busca |
| `generate_answer` | responde à mensagem do turno só com os trechos da última busca e com o histórico da conversa, citando documento e página |

Estado:

```python
class TriageState(MessagesState):
    question: str      # mensagem do usuário neste turno; a reescrita não a altera
    rewrites: int      # reescritas feitas neste turno
    grade: dict        # última avaliação dos trechos: binary_score e reason
```

### Decisões

**A pergunta fica no estado.** No notebook de RAG agêntico da disciplina, a pergunta é a primeira mensagem do histórico, o que só funciona com um turno. Com memória, a primeira mensagem é a do começo da conversa. O `start_turn` guarda a mensagem do turno em `question`, e a avaliação, a reescrita e a resposta usam esse campo.

**A avaliação é um nó.** A reescrita usa o motivo da reprovação ("os trechos falam da definição de caso, mas não da conduta") para procurar por outro ângulo, e para isso a avaliação precisa ser gravada no estado. Ela é um nó que devolve um `Command` com a atualização e o próximo nó.

**A reescrita vai direto para a busca.** O `rewrite_question` devolve uma `AIMessage` com a chamada ao `search_protocolos` já montada, e o grafo vai para o `retrieve` sem passar de novo pelo modelo com ferramentas. Isso economiza uma chamada por reescrita e não insere no histórico uma mensagem de usuário que o usuário não escreveu.

**O avaliador recebe a consulta, além da mensagem.** Em uma conversa, "agora minha gengiva tá sangrando" só faz sentido com os turnos anteriores. O avaliador recebe a mensagem e a consulta que o modelo escreveu, que já junta os dados da conversa.

**O histórico vai enxuto para o modelo.** Dos turnos anteriores, entram só as mensagens do usuário e as respostas finais. Os trechos recuperados em turnos passados custariam milhares de tokens a cada chamada, e a resposta que saiu deles já está no histórico.

**Busca com MMR.** O manual de enfermagem repete trechos inteiros do manual de manejo, e a busca por similaridade gastava metade dos lugares com a mesma informação. Na pergunta de um paciente sem sinais de alarme, o trecho da conduta do grupo A ficava em oitavo. Com MMR (`k=5`, `fetch_k=20`, `lambda_mult=0.7`), ele entra entre os cinco.

**Uma reescrita por turno.** Cada chamada ao modelo conta no limite do plano gratuito, de 15 por minuto e 500 por dia. O turno comum gasta três chamadas (decidir, avaliar, responder), e o pior caso, com uma reescrita, cinco. O `MAX_REWRITES` fica em 1.

**Sem roteador na entrada.** Um nó de roteamento custaria uma chamada a mais em todo turno, e o `generate_query_or_respond` já separa o que precisa de busca do que não precisa. Respostas diretas se limitam a mensagens fixas de conversa social, escopo ou informação insuficiente.

## Modelo e limites

O modelo é o Gemini 3.5 Flash Lite, e o embedding, o Gemini Embedding 2, os dois pelo plano gratuito do Google AI Studio. Os limites do plano gratuito definem boa parte do desenho:

| Modelo | Requisições/min | Tokens/min | Requisições/dia |
|---|---|---|---|
| Gemini 3.5 Flash Lite | 15 | 250 mil | 500 |
| Gemini Embedding 2 | 100 | 30 mil | 1000 |

Um `InMemoryRateLimiter` único para o processo segura as chamadas de chat em 12 por minuto (`MODEL_RPM`). Ele é compartilhado porque o grafo chama o modelo em vários nós, e um limitador por nó deixaria a soma passar do limite. A indexação inteira gasta cerca de 107 mil tokens de embedding e leva uns cinco minutos com `EMBEDDINGS_TPM=25000`. Cada busca gasta uma requisição de embedding para a consulta.

## Como rodar

Na raiz do projeto, com a chave já configurada no `.env`, execute:

```bash
uv sync
uv run triagem
```

Em um clone novo, copie `.env.example` para `.env` e preencha `GOOGLE_API_KEY` uma vez. O aplicativo baixa os manuais ausentes, completa os embeddings que faltam e abre o Streamlit. Nas próximas execuções, `uv run triagem` verifica a base local e abre a interface. Se a indexação for interrompida, repita o mesmo comando para retomar. O terminal exibe o endereço local da interface.

Para usar o chat pelo terminal com a base preparada, execute `uv run python -m triagem.terminal`.

O terminal mostra os nós percorridos, a avaliação dos trechos, os nomes das ferramentas chamadas e as skills carregadas em cada turno. A versão do MCP Time é instalada com as demais dependências do projeto. O terminal também aceita as mensagens como argumentos, cada uma como um turno da mesma conversa:

```bash
uv run python -m triagem.terminal "Febre há 3 dias e manchas no corpo" "Agora minha gengiva tá sangrando"
```

O terminal mostra o UUID da conversa na abertura. Para retomar essa conversa em outra execução, use `uv run python -m triagem.terminal --thread-id UUID`. Sem essa opção, o terminal cria uma nova conversa. Use relatos sintéticos na demonstração. O arquivo local `checkpoints.db` armazena as mensagens e o estado do grafo.

Variáveis de ambiente (`.env`):

| Variável | Uso |
|---|---|
| `GOOGLE_API_KEY` | chave do Google AI Studio |
| `MODEL` | modelo de chat, no formato do `init_chat_model` (padrão `google_genai:gemini-3.5-flash-lite`) |
| `EMBEDDINGS` | modelo de embedding, no formato do `init_embeddings` (padrão `google_genai:gemini-embedding-2`). Ao trocar, apague `chroma_arboviroses/` e indexe de novo, porque o tamanho do vetor muda |
| `MODEL_RPM` | chamadas de chat por minuto (padrão 12) |
| `EMBEDDINGS_TPM` | tokens de embedding por minuto na indexação (padrão 25000) |

## Estrutura

```text
├── coletor/agente.py      # baixa os PDFs: pelo manifesto ou com o agente
├── documentos/fontes.json # origem de cada documento
└── src/triagem/
    ├── settings.py        # caminhos, modelos e limitador de requisições
    ├── indice.py          # leitura dos PDFs, corte e indexação no Chroma
    ├── rag.py             # search_protocolos, avaliador e reescrita
    ├── grafo.py           # estado, nós, arestas e build_graph
    └── terminal.py        # chat de terminal para testar o grafo
```

## MCP, skills e memória

- `mcp_servidor.py` oferece `listar_fontes_oficiais` e `resumir_checklist_triagem` via MCP por stdio. `mcp_cliente.py` conecta esse servidor e o [MCP Time](https://github.com/modelcontextprotocol/servers/tree/main/src/time), que fornece a data.
- `skills_loader.py` envia o catálogo à mensagem de sistema. O modelo carrega as instruções de triagem inicial ou reavaliação com `load_skill` antes da busca, em uma chamada separada. Os arquivos ficam em `src/triagem/skills/`.
- `runtime.py` conecta ferramentas, catálogo e checkpointer ao grafo existente. `memoria.py` abre o SQLite, e cada turno envia somente a mensagem nova com o UUID da conversa. O registro de execução expõe os nomes das ferramentas e as skills carregadas para o terminal e para a interface Streamlit.

## Guardrails e interface

O filtro local de entrada reconhece expressões de alarme como “estou vomitando sangue” e prioriza uma orientação fixa de urgência antes da busca. Também limita o tamanho do relato e intercepta pedidos explícitos para ignorar as instruções. As expressões cobrem exemplos frequentes. O fluxo clínico continua consultando os manuais para outros relatos. Os sinais usados como referência estão no [Observatório de Arboviroses do Ministério da Saúde](https://www.gov.br/saude/pt-br/composicao/svsa/cnie/observatorio-de-arboviroses/sinais-de-alerta).

Na saída clínica, uma avaliação negativa após a reescrita encerra o turno com uma resposta de informação insuficiente. O filtro exige ao menos uma referência, confere se todas as páginas citadas vieram da busca atual e intercepta padrões de dose numérica e afirmações diretas de diagnóstico. A conferência verifica a referência disponível, sem validar clinicamente cada afirmação.

O chat mantém a conversa entre envios, mostra as ferramentas e skills usadas e abre outra sessão ao clicar em **Nova conversa**. A barra lateral reabre as conversas pelo título. A interface salva um JSON por conversa em `conversas/` e usa o mesmo UUID para retomar a memória no SQLite. O histórico é local e compartilhado por quem acessa esta instância.

Configure uma chave própria no arquivo local `.env`. O Git ignora as configurações locais e inclui o modelo vazio `.env.example`. Se uma chave anterior foi publicada, revogue-a no Google AI Studio e substitua o valor local.
