# Casos de Uso — Nexus

Os casos de uso cobrem os fluxos principais do MVP.

---

## UC-01 — Criar Assistente

| Campo | Descrição |
|-------|-----------|
| **Nome** | Criar Assistente |
| **Objetivo** | Permitir que o usuário registre um novo assistente com sua base de conhecimento isolada. |
| **Ator principal** | Usuário |
| **Pré-condição** | O sistema está em execução e a interface está acessível. |
| **Fluxo principal** | 1. O usuário acessa a tela inicial e clica em "Criar assistente". <br>2. O sistema exibe o modal de criação com campos de nome, descrição e prompt inicial. <br>3. O usuário preenche o nome (obrigatório) e os demais campos opcionais. <br>4. O usuário confirma a criação. <br>5. O sistema persiste o assistente e exibe o card na lista. |
| **Fluxo alternativo** | 4a. O usuário tenta confirmar sem preencher o nome. O sistema exibe erro de validação e mantém o modal aberto. |
| **Pós-condição** | O assistente está cadastrado e disponível para receber documentos e conversas. |

---

## UC-02 — Enviar Documento para Assistente

| Campo | Descrição |
|-------|-----------|
| **Nome** | Enviar Documento |
| **Objetivo** | Adicionar conhecimento a um assistente por meio do upload de um arquivo. |
| **Ator principal** | Usuário |
| **Pré-condição** | Pelo menos um assistente está cadastrado. |
| **Fluxo principal** | 1. O usuário seleciona um assistente. <br>2. O usuário acessa a seção de documentos e clica em "Enviar documento". <br>3. O usuário seleciona um arquivo nos formatos suportados (PDF, TXT, MD, DOC, DOCX). <br>4. O sistema confirma o recebimento, extrai o texto, gera chunks, calcula embeddings e indexa na collection do assistente no Qdrant. <br>5. O sistema informa o sucesso da indexação. |
| **Fluxo alternativo** | 3a. O arquivo está em formato não suportado. O sistema rejeita e informa os formatos aceitos. |
| **Pós-condição** | O conteúdo do documento está indexado e disponível para busca nas conversas do assistente. |

---

## UC-03 — Conversar com Assistente (RAG)

| Campo | Descrição |
|-------|-----------|
| **Nome** | Enviar Mensagem no Chat |
| **Objetivo** | Permitir que o usuário faça perguntas em linguagem natural e receba respostas baseadas nos documentos do assistente. |
| **Ator principal** | Usuário |
| **Pré-condição** | Um assistente com documentos indexados está selecionado; a chave de API do LLM está configurada. |
| **Fluxo principal** | 1. O usuário digita uma pergunta no campo de entrada e clica em "Enviar". <br>2. O sistema recupera os `top-k` chunks mais relevantes da base vetorial do assistente. <br>3. O sistema constrói o prompt com o histórico da conversa e os chunks recuperados. <br>4. O sistema envia o prompt ao LLM e transmite a resposta em streaming. <br>5. A resposta é exibida no chat e persistida no histórico. |
| **Fluxo alternativo** | 2a. Nenhum chunk relevante é encontrado. O LLM é informado que não há contexto e gera uma resposta indicando ausência de informação na base. <br>4a. O LLM retorna erro (timeout, quota). O sistema exibe mensagem de falha sem perder o histórico anterior. |
| **Pós-condição** | A mensagem e a resposta estão persistidas no histórico da conversa. |

---

## UC-04 — Inferência Automática de Assistente

| Campo | Descrição |
|-------|-----------|
| **Nome** | Inferir Assistente e Enviar Mensagem |
| **Objetivo** | Identificar automaticamente o assistente mais adequado para uma pergunta sem exigir seleção manual. |
| **Ator principal** | Usuário |
| **Pré-condição** | Nenhum assistente está selecionado; há pelo menos um assistente cadastrado; a chave de API do LLM está configurada. |
| **Fluxo principal** | 1. O usuário digita uma pergunta e clica em "Enviar". <br>2. O sistema exibe o indicador de inferência. <br>3. O sistema chama `POST /api/assistants/infer` com a pergunta. <br>4. O backend executa o fluxo LangGraph: constrói prompt de classificação com a lista de assistentes, chama o LLM, analisa a resposta e valida o `assistant_id`. <br>5. O sistema retorna o `assistant_id` inferido. <br>6. O sistema seleciona automaticamente o assistente e executa o UC-03. |
| **Fluxo alternativo** | 5a. O LLM não consegue inferir nenhum assistente (`null`). O sistema exibe o popup de aviso (RF-23) e aguarda ação do usuário. <br>5b. Erro de comunicação com a API. O sistema exibe mensagem de falha e permite nova tentativa. |
| **Pós-condição** | O assistente está selecionado e a conversa foi iniciada, **ou** o popup de aviso está visível para reorientação do usuário. |

---

## UC-05 — Configurar Chave de API do LLM

| Campo | Descrição |
|-------|-----------|
| **Nome** | Configurar Chave de API |
| **Objetivo** | Permitir ao administrador cadastrar ou atualizar a chave de acesso ao provedor LLM. |
| **Ator principal** | Administrador / Usuário |
| **Pré-condição** | O sistema está em execução. |
| **Fluxo principal** | 1. O usuário acessa o painel de administração. <br>2. O sistema exibe o status atual da chave (configurada / não configurada). <br>3. O usuário insere a nova chave e confirma. <br>4. O sistema criptografa a chave com Fernet e persiste no banco de dados. <br>5. O sistema atualiza o status exibido para "Configurada". |
| **Fluxo alternativo** | 3a. O usuário deixa o campo em branco e confirma. O sistema exibe erro de validação. |
| **Pós-condição** | A chave está armazenada criptografada e o sistema passa a usá-la nas requisições ao LLM. |
