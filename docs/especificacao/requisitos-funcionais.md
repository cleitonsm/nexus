# Requisitos Funcionais — Nexus

Origem: análise das entrevistas, documentos de negócio e codebase do MVP.
Notação: `RF-XX` — Requisito Funcional.

---

## Módulo: Assistentes

| ID    | Descrição |
|-------|-----------|
| RF-01 | O sistema deve permitir criar um assistente informando nome, descrição opcional e prompt inicial opcional. |
| RF-02 | O sistema deve listar todos os assistentes cadastrados. |
| RF-03 | O sistema deve permitir excluir um assistente, removendo também sua base de documentos e histórico de conversas associados. |
| RF-04 | O sistema deve permitir selecionar um assistente ativo para iniciar ou retomar conversas. |
| RF-05 | O sistema deve inferir automaticamente o assistente mais adequado para responder a uma pergunta quando nenhum assistente estiver selecionado, utilizando um fluxo LangGraph de classificação via LLM. |

## Módulo: Documentos / Base de Conhecimento

| ID    | Descrição |
|-------|-----------|
| RF-06 | O sistema deve permitir o upload de documentos (PDF, TXT, MD, DOC, DOCX) vinculados a um assistente específico. |
| RF-07 | O sistema deve extrair, fragmentar (chunking) e indexar automaticamente o conteúdo dos documentos enviados na base vetorial do assistente correspondente. |
| RF-08 | O sistema deve garantir que a base de conhecimento de cada assistente seja isolada das demais, impedindo mistura de contextos. |

## Módulo: Conversas e Chat

| ID    | Descrição |
|-------|-----------|
| RF-09 | O sistema deve permitir criar uma nova conversa associada a um assistente. |
| RF-10 | O sistema deve enviar uma mensagem do usuário, recuperar os trechos mais relevantes da base vetorial do assistente e gerar uma resposta contextualizada. |
| RF-11 | O sistema deve persistir o histórico completo de mensagens de cada conversa. |
| RF-12 | O sistema deve nomear a conversa automaticamente a partir do conteúdo da primeira mensagem do usuário. |
| RF-13 | O sistema deve permitir listar as conversas de um assistente. |
| RF-14 | O sistema deve permitir carregar e exibir as mensagens de uma conversa previamente salva. |
| RF-15 | O sistema deve permitir excluir uma conversa e seu histórico de mensagens. |

## Módulo: Configuração de LLM

| ID    | Descrição |
|-------|-----------|
| RF-16 | O sistema deve permitir configurar e persistir de forma criptografada a chave de API do provedor LLM global. |
| RF-17 | O sistema deve exibir o status atual da chave de API (configurada / não configurada). |
| RF-18 | O sistema deve permitir testar a conectividade com o provedor LLM usando a chave cadastrada, retornando resultado e prévia da resposta. |

## Módulo: Interface (Frontend)

| ID    | Descrição |
|-------|-----------|
| RF-19 | O sistema deve exibir cards de boas-vindas na tela inicial quando não houver assistentes cadastrados, com atalho para criação do primeiro assistente. |
| RF-20 | O sistema deve exibir os três assistentes mais recentes como cards de seleção rápida na tela inicial quando houver assistentes cadastrados. |
| RF-21 | O sistema deve exibir uma tela de chat com área de mensagens, campo de entrada e botão de envio. |
| RF-22 | O sistema deve exibir um indicador de carregamento (spinner) enquanto a inferência automática de assistente estiver em andamento. |
| RF-23 | O sistema deve exibir um popup de aviso quando não for possível inferir o assistente adequado, orientando o usuário a reformular a pergunta ou selecionar manualmente um assistente. |

---

# Evolução — RAG Enterprise

Origem: estudo de lacunas do pipeline de RAG do MVP e plano de evolução em seis fases
(ver [`docs/plano-incremental.md`](../plano-incremental.md), etapas 9 a 14).
Cada módulo corresponde a uma fase e a uma especificação SDD em [`specs/`](specs/README.md).

**Situação em 2026-10-07:** os requisitos da Fase 1 (RF-24 a RF-27) estão implementados e em
validação no ambiente Docker; os das Fases 2 a 6 (RF-28 a RF-63) ainda não foram implementados.

Requisitos do MVP revisados por esta evolução:

- **RF-07** passa a ser atendido de forma assíncrona (RF-48) e com chunking estrutural (RF-29).
- **RF-10** passa a incluir busca híbrida, reranking e citações (RF-33 a RF-37).

## Módulo: Avaliação e Qualidade (Fase 1 — implementado, em validação)

| ID    | Descrição |
|-------|-----------|
| RF-24 | O sistema deve manter, por assistente, um conjunto de referência versionado no repositório, em que cada item contém a pergunta, a resposta esperada e o documento de origem. |
| RF-25 | O sistema deve oferecer um comando de avaliação que executa o pipeline de RAG contra o conjunto de referência e calcula recall@k, MRR, fidelidade da resposta ao contexto e taxa de fallback correto. |
| RF-26 | O sistema deve gravar um relatório de cada avaliação, identificando commit, modelos e parâmetros utilizados, e comparar o resultado com a execução anterior. |
| RF-27 | O sistema deve emitir logs estruturados em JSON com um identificador de requisição propagado por todas as etapas do processamento. |

## Módulo: Recuperação Semântica (Fase 2)

| ID    | Descrição |
|-------|-----------|
| RF-28 | O sistema deve gerar embeddings com um modelo semântico multilíngue executado localmente, definido por `EMBEDDING_MODEL_NAME`, sem chamadas a serviços externos (ADR 0004). |
| RF-29 | O sistema deve fragmentar os documentos respeitando sua estrutura (títulos, parágrafos, listas e tabelas), com tamanho medido em tokens e limitado à capacidade do modelo de embedding. |
| RF-30 | O sistema deve gravar em cada chunk, além dos metadados mínimos do MVP, o título da seção, a página de origem e o modelo de embedding utilizado. |
| RF-31 | O sistema deve permitir reindexar a base de um assistente sem indisponibilidade, construindo uma nova collection e trocando o alias somente ao final. |
| RF-32 | O sistema deve registrar, por documento, o modelo de embedding e a versão do pipeline de ingestão, e sinalizar bases indexadas com configuração diferente da vigente. |

## Módulo: Busca Híbrida, Reranking e Citações (Fase 3)

| ID    | Descrição |
|-------|-----------|
| RF-33 | O sistema deve recuperar candidatos por busca híbrida, combinando vetor denso e vetor esparso (BM25) com fusão por Reciprocal Rank Fusion. |
| RF-34 | O sistema deve reordenar os candidatos recuperados com um modelo de reranking executado localmente e manter apenas os melhores para compor o contexto. |
| RF-35 | O sistema deve descartar candidatos abaixo de uma nota mínima de relevância configurável e acionar o fallback, sem chamar o LLM, quando nenhum candidato a atingir. |
| RF-36 | O sistema deve reescrever a pergunta do usuário em uma consulta autônoma, usando o histórico da conversa, antes de executar a busca. |
| RF-37 | O sistema deve devolver, junto com cada resposta gerada, as citações dos trechos utilizados (documento, seção e página) e persisti-las com a mensagem. |
| RF-38 | O sistema deve exibir no chat as fontes de cada resposta, permitindo consultar o trecho citado. |
| RF-39 | O sistema deve limitar o histórico e o contexto enviados ao LLM a um orçamento de tokens configurável, priorizando as mensagens mais recentes e os trechos mais bem classificados. |

## Módulo: Autenticação e Controle de Acesso (Fase 4)

| ID    | Descrição |
|-------|-----------|
| RF-40 | O sistema deve autenticar usuários exclusivamente pelo Keycloak, via OpenID Connect (Authorization Code com PKCE), e exigir token válido em todas as rotas da API, exceto `/health`. |
| RF-41 | O sistema deve reconhecer os papéis administrador, curador e usuário a partir do token emitido pelo Keycloak. |
| RF-42 | O sistema deve permitir vincular assistentes a grupos do Keycloak e exibir a cada usuário apenas os assistentes aos quais seus grupos têm acesso. |
| RF-43 | O sistema deve permitir restringir um documento a grupos específicos e aplicar essa restrição como filtro obrigatório na busca vetorial. |
| RF-44 | O sistema deve associar cada conversa ao usuário que a criou e permitir o acesso ao seu conteúdo apenas a esse usuário. |
| RF-45 | O sistema deve registrar trilha de auditoria de autenticações, perguntas realizadas, documentos recuperados e alterações em assistentes, documentos e permissões. |
| RF-46 | O frontend deve oferecer login, logout e renovação de sessão pelo Keycloak e ocultar funcionalidades para as quais o usuário não tem permissão. |
| RF-47 | O sistema deve restringir ao papel administrador a configuração e o teste da chave de API do LLM. |

## Módulo: Ingestão e Ciclo de Vida de Documentos (Fase 5)

| ID    | Descrição |
|-------|-----------|
| RF-48 | O sistema deve processar a ingestão de forma assíncrona: o upload registra o documento, armazena o arquivo original e enfileira o processamento. |
| RF-49 | O sistema deve expor e exibir o estado de cada documento (pendente, processando, indexado, falhou) e o motivo em caso de falha. |
| RF-50 | O sistema deve permitir excluir um documento, removendo seus vetores e o arquivo original. |
| RF-51 | O sistema deve permitir substituir um documento por uma nova versão, mantendo a versão anterior ativa até a nova estar indexada. |
| RF-52 | O sistema deve detectar o envio de arquivo idêntico a um documento já existente no mesmo assistente e informar o usuário em vez de duplicar o conteúdo. |
| RF-53 | O sistema deve extrair texto de PDFs digitalizados por OCR executado localmente e preservar o conteúdo de tabelas. |
| RF-54 | O sistema deve armazenar o arquivo original de cada documento e permitir reprocessá-lo sem novo upload. |
| RF-55 | O sistema deve repetir automaticamente o processamento de um documento em caso de falha transitória, até um número máximo de tentativas. |

## Módulo: Operação e Governança (Fase 6)

| ID    | Descrição |
|-------|-----------|
| RF-56 | O sistema deve registrar rastreamento distribuído de cada resposta, com um trecho (span) por etapa do grafo conversacional. |
| RF-57 | O sistema deve expor métricas de latência por etapa, consumo de tokens e custo estimado por conversa. |
| RF-58 | O sistema deve transmitir a resposta do chat em streaming à medida que o LLM a gera. |
| RF-59 | O sistema deve aplicar limite de uso por usuário e tamanho máximo de upload, ambos configuráveis. |
| RF-60 | O sistema deve tratar o conteúdo recuperado dos documentos como dado delimitado no prompt, nunca como instrução, e registrar tentativas detectadas de injeção de prompt. |
| RF-61 | O sistema deve permitir ao usuário avaliar cada resposta como útil ou não útil, com comentário opcional. |
| RF-62 | O sistema deve executar a avaliação de qualidade na integração contínua e bloquear mudanças que causem regressão acima da tolerância configurada. |
| RF-63 | O sistema deve oferecer rotina de backup do PostgreSQL e de snapshot do Qdrant, com procedimento de restauração documentado. |
