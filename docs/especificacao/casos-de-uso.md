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

---

# Evolução — RAG Enterprise

Os casos de uso abaixo descrevem a evolução planejada. Em 2026-10-07, apenas o UC-12 (avaliação de
qualidade) está implementado, em validação no ambiente Docker; os demais ainda não estão.
UC-08 e UC-10 revisam, respectivamente, UC-02 e UC-03; os fluxos do MVP permanecem válidos até a
entrega das fases correspondentes.

---

## UC-06 — Autenticar-se no Nexus

| Campo | Descrição |
|-------|-----------|
| **Nome** | Autenticar-se pelo Keycloak |
| **Objetivo** | Identificar o usuário e carregar seus papéis e grupos antes de qualquer uso do sistema. |
| **Ator principal** | Usuário, Curador ou Administrador |
| **Ator secundário** | Keycloak |
| **Pré-condição** | O usuário possui conta no realm `nexus` do Keycloak. |
| **Fluxo principal** | 1. O usuário acessa o Nexus sem sessão ativa. <br>2. O frontend redireciona para o Keycloak (Authorization Code com PKCE). <br>3. O usuário informa suas credenciais no Keycloak. <br>4. O Keycloak devolve o código de autorização e o frontend obtém os tokens. <br>5. O frontend envia o token de acesso em cada chamada à API. <br>6. O backend valida o token e extrai identificador, papéis e grupos. <br>7. O sistema exibe a interface conforme o papel do usuário e registra o acesso na auditoria. |
| **Fluxo alternativo** | 3a. Credenciais inválidas. O Keycloak exibe o erro e o usuário permanece na tela de login. <br>5a. O token expirou. O frontend renova a sessão de forma transparente; se não for possível, redireciona para o login. <br>6a. O token é inválido. A API responde 401 e nenhum dado é retornado. |
| **Pós-condição** | O usuário está autenticado e suas requisições carregam identidade, papéis e grupos. |

---

## UC-07 — Gerenciar Acesso a Assistente

| Campo | Descrição |
|-------|-----------|
| **Nome** | Vincular Grupos a um Assistente |
| **Objetivo** | Definir quais grupos podem ver e usar um assistente. |
| **Ator principal** | Administrador |
| **Pré-condição** | O administrador está autenticado; o assistente existe; os grupos existem no Keycloak. |
| **Fluxo principal** | 1. O administrador abre as permissões do assistente. <br>2. O sistema exibe os grupos atualmente vinculados. <br>3. O administrador adiciona ou remove grupos e confirma. <br>4. O sistema persiste os vínculos e registra o evento na auditoria. <br>5. A alteração passa a valer na próxima requisição dos usuários afetados. |
| **Fluxo alternativo** | 3a. O administrador remove todos os grupos. O sistema avisa que o assistente ficará visível apenas a administradores (RN-22) e pede confirmação. <br>1a. Um usuário sem papel administrador tenta acessar a funcionalidade. A API responde 403. |
| **Pós-condição** | Apenas usuários dos grupos vinculados visualizam e conversam com o assistente. |

---

## UC-08 — Enviar Documento (Ingestão Assíncrona)

| Campo | Descrição |
|-------|-----------|
| **Nome** | Enviar Documento em Segundo Plano |
| **Objetivo** | Adicionar conhecimento a um assistente sem bloquear o curador durante o processamento. |
| **Ator principal** | Curador |
| **Ator secundário** | Worker de ingestão |
| **Pré-condição** | O curador está autenticado e tem acesso ao assistente. |
| **Fluxo principal** | 1. O curador seleciona o assistente e envia um arquivo em formato suportado. <br>2. O sistema valida formato e tamanho, calcula o `content_hash` e verifica duplicidade. <br>3. O sistema armazena o arquivo original, registra o documento no estado "pendente" e enfileira o processamento. <br>4. A API responde imediatamente com o identificador e o estado. <br>5. O worker assume o job, muda o estado para "processando", extrai o texto (com OCR quando necessário), fragmenta por estrutura, gera vetores denso e esparso localmente e grava na collection do assistente. <br>6. O worker muda o estado para "indexado". <br>7. A interface atualiza o estado sem recarregar a página. |
| **Fluxo alternativo** | 2a. Formato não suportado ou arquivo acima de 25 MB. O sistema rejeita e informa o motivo. <br>2b. Arquivo idêntico já existe no assistente. O sistema informa o documento existente e não cria outro (RN-26). <br>5a. Falha transitória no processamento. O job é reagendado até o limite de três tentativas. <br>5b. Falha definitiva. O estado muda para "falhou" com o motivo registrado; o curador pode reprocessar. |
| **Pós-condição** | O documento está indexado e disponível para busca, **ou** está no estado "falhou" com o motivo visível. |

---

## UC-09 — Excluir ou Substituir Documento

| Campo | Descrição |
|-------|-----------|
| **Nome** | Gerenciar Ciclo de Vida de Documento |
| **Objetivo** | Manter a base de um assistente atual, removendo ou atualizando documentos. |
| **Ator principal** | Curador |
| **Pré-condição** | O curador está autenticado e tem acesso ao assistente; o documento existe. |
| **Fluxo principal (excluir)** | 1. O curador seleciona o documento e solicita a exclusão. <br>2. O sistema pede confirmação. <br>3. O sistema remove os vetores do documento, o arquivo original e o registro, e grava o evento na auditoria. <br>4. O documento deixa de aparecer na lista e nas buscas. |
| **Fluxo principal (substituir)** | 1. O curador seleciona o documento e envia a nova versão. <br>2. O sistema registra a nova versão como "pendente" e mantém a anterior ativa. <br>3. O worker processa a nova versão (UC-08, passos 5 e 6). <br>4. Ao concluir, o sistema remove os vetores da versão anterior e passa a servir apenas a nova. |
| **Fluxo alternativo** | 3a (substituir). O processamento da nova versão falha. A versão anterior permanece ativa (RN-28) e o curador é informado. |
| **Pós-condição** | A base reflete a exclusão ou a nova versão, sem período de indisponibilidade do conteúdo. |

---

## UC-10 — Conversar com Assistente (RAG com Citações)

| Campo | Descrição |
|-------|-----------|
| **Nome** | Enviar Mensagem no Chat com Fontes |
| **Objetivo** | Responder perguntas em linguagem natural com base nos documentos a que o usuário tem acesso, indicando as fontes. |
| **Ator principal** | Usuário |
| **Ator secundário** | Provedor de LLM |
| **Pré-condição** | O usuário está autenticado e tem acesso ao assistente; a chave de API do LLM está configurada. |
| **Fluxo principal** | 1. O usuário envia uma pergunta. <br>2. O sistema verifica a permissão do usuário sobre o assistente e o limite de uso. <br>3. O sistema carrega o histórico e reescreve a pergunta como consulta autônoma. <br>4. O sistema executa a busca híbrida na collection do assistente, com filtro pelos grupos do usuário. <br>5. O sistema reordena os candidatos e descarta os que ficam abaixo da nota mínima. <br>6. O sistema monta o prompt com histórico e contexto dentro do orçamento de tokens, delimitando os trechos como dados. <br>7. O sistema chama o LLM e transmite a resposta em streaming. <br>8. O sistema valida as citações, persiste pergunta, resposta e fontes e registra o evento na auditoria. <br>9. A interface exibe a resposta e suas fontes. |
| **Fluxo alternativo** | 2a. O usuário não tem acesso ao assistente. A API responde 403. <br>2b. O limite de uso foi atingido. A API responde 429 com orientação (RN-32). <br>5a. Nenhum candidato atinge a nota mínima. O sistema responde com o fallback sem chamar o LLM (RN-17). <br>7a. O LLM retorna erro ou excede o tempo limite. O sistema informa a falha sem perder o histórico. <br>8a. A resposta não contém citação válida. O sistema a substitui pelo fallback (RN-18). |
| **Pós-condição** | Pergunta, resposta e fontes estão persistidas; o evento está na auditoria. |

---

## UC-11 — Reindexar Base de um Assistente

| Campo | Descrição |
|-------|-----------|
| **Nome** | Reindexar sem Indisponibilidade |
| **Objetivo** | Reconstruir os vetores de um assistente após mudança de modelo de embedding ou de estratégia de chunking. |
| **Ator principal** | Administrador |
| **Ator secundário** | Worker de ingestão |
| **Pré-condição** | Os arquivos originais dos documentos do assistente estão armazenados. |
| **Fluxo principal** | 1. O administrador solicita a reindexação do assistente. <br>2. O sistema cria uma nova collection versionada. <br>3. O worker reprocessa cada documento a partir do arquivo original e grava na nova collection. <br>4. O sistema confere a contagem de documentos e chunks. <br>5. O sistema troca o alias do assistente para a nova collection. <br>6. O sistema remove a collection anterior e registra o evento na auditoria. |
| **Fluxo alternativo** | 3a. Um documento não possui arquivo original (ingerido antes da Fase 5). O sistema lista os documentos pendentes de novo upload e não troca o alias. <br>4a. A conferência falha. O sistema descarta a nova collection e mantém a vigente. |
| **Pós-condição** | O assistente responde com a base reindexada, **ou** a base anterior permanece intacta. |

---

## UC-12 — Executar Avaliação de Qualidade

| Campo | Descrição |
|-------|-----------|
| **Nome** | Avaliar o Pipeline de RAG |
| **Objetivo** | Medir recuperação e resposta contra o conjunto de referência e comparar com a execução anterior. |
| **Ator principal** | Equipe técnica |
| **Pré-condição** | O conjunto de referência do assistente existe e foi validado por um curador. |
| **Fluxo principal** | 1. A equipe técnica executa o comando de avaliação informando o assistente. <br>2. O sistema valida o formato do conjunto de referência. <br>3. Para cada pergunta, o sistema executa a recuperação e a geração. <br>4. O sistema calcula recall@k, MRR, fidelidade e taxa de fallback correto. <br>5. O sistema grava o relatório com commit, modelos e parâmetros e compara com o relatório anterior. |
| **Fluxo alternativo** | 2a. O conjunto contém itens inválidos. O sistema lista os itens e encerra sem avaliar. <br>5a. Há regressão acima da tolerância. O comando termina com código de erro, bloqueando a integração contínua. |
| **Pós-condição** | O relatório de avaliação está disponível e a mudança está aprovada ou bloqueada. |

---

## UC-13 — Consultar Trilha de Auditoria

| Campo | Descrição |
|-------|-----------|
| **Nome** | Consultar Auditoria |
| **Objetivo** | Permitir verificar quem acessou, perguntou ou alterou a base de conhecimento. |
| **Ator principal** | Administrador |
| **Pré-condição** | O administrador está autenticado. |
| **Fluxo principal** | 1. O administrador acessa a auditoria. <br>2. O administrador filtra por período, usuário, assistente ou tipo de evento. <br>3. O sistema exibe os eventos com data, autor, ação e recursos envolvidos. |
| **Fluxo alternativo** | 1a. Um usuário sem papel administrador tenta acessar. A API responde 403. |
| **Pós-condição** | Nenhum dado é alterado; a própria consulta é registrada na auditoria. |
