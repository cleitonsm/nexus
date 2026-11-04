# SPEC-018 — Resumidor de documentos (assistente de sistema com resumo hierárquico)

**ID**: SPEC-20261030-018
**Status**: **Implementada com ressalva** em 2026-11-04 — [validação](../../qa/relatorios/2026-10-30-spec-018/LEIAME.md): CT-139 a CT-151 aprovados (RNF-37 em 0,19 s; RNF-40 em 357,6 s antes da D44); a nova medição do RNF-40 com a D44, a avaliação de não regressão e o CT-152 ficaram pendentes por falta de crédito no provedor de LLM, por decisão do autor. Histórico: **Aprovada** em 2026-10-30 pelo autor (Cleiton Medeiros); **Rascunho** em 2026-10-30; o autor aprovou **todas as recomendações** de D1 a D43 e as escolhas A e B, registradas em `SPEC-018-decisoes-resumidor.xlsx`. Em 2026-10-30, na validação (P9), o autor acrescentou a **D44** (mini-resumos em paralelo) depois da medição do RNF-40.
**Origem**: pedido do autor (2026-10-30): um assistente específico para resumir documentos Word, TXT e PDF, sempre disponível no acesso rápido, padrão para quem ainda não escolheu outro, e capaz de explicar a própria finalidade e os limites antes do primeiro envio. Também o requisito "Pipeline de Ingestão Assíncrona, Resumo Hierárquico e Indexação Vetorial de Documentos Extensos" (RN01 a RN06 e critérios 1 a 5), adaptado ao Nexus conforme a seção "Rastreabilidade do requisito de origem".
**Plano**: [SPEC-018-plano-de-implementacao.md](SPEC-018-plano-de-implementacao.md)
**ADR**: [0014 — Documento pessoal e assistente de sistema](../../arquitetura/adrs/0014-documento-pessoal-e-assistente-de-sistema.md)
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

1. Hoje todo assistente responde com base em documentos que um **administrador ou curador** envia para a base dele (SPEC-005). O usuário comum **não envia arquivo**. Por isso não existe no Nexus uma forma de resumir um documento próprio.
2. Parte do pipeline necessário já existe e é reaproveitada:
   - extração de `.txt`, `.md`, `.markdown`, `.pdf`, `.doc` e `.docx`, com OCR por Tesseract em PDF escaneado (`infrastructure/documents`);
   - upload com teto de 25 MB e resposta 413 (`api/uploads.py`, `UPLOAD_MAX_BYTES`);
   - fila de ingestão no PostgreSQL (`ingestion_jobs`), consumida pelo worker (`cli/worker.py`), com 3 tentativas, limite de 600 s por job e status consultado pela tela a cada 3 s (ADR 0009);
   - divisão estrutural em seções (`infrastructure/chunking/structural_chunker.py`), embeddings locais de 128 tokens (ADR 0004 e 0006), busca híbrida, reranking e citações `[n]` (SPEC-003);
   - filtro de payload genérico na busca (`payload_filter` em `QdrantVectorStoreGateway.hybrid_search`), além dos filtros de `user_groups` e `active`;
   - registro de uso e custo em USD por usuário (`usage_records`, SPEC-006) e trilha de auditoria append-only.
3. O que falta:
   - o conceito de **documento pessoal**, que pertence a um usuário e a uma conversa, não à base do assistente;
   - o conceito de **assistente de sistema**, que existe sem ser criado por um administrador, é visível a todos e não pode ser excluído;
   - o **resumo hierárquico** gravado (mini-resumos por seção mais um consolidado) e a entrega dele sem chamada ao LLM;
   - um **teto em tokens** por documento;
   - a regra do acesso rápido (SPEC-016) para um cartão fixo que não ocupa vaga.
4. A RN03 do requisito de origem (chunks de 500 a 1.000 tokens com sobreposição de 100 a 200) **fica fora** (escolha A): o modelo local de embeddings aceita 128 tokens. O resumo não usa esses chunks. Ele trabalha sobre lotes de seções de 4 a 8 mil tokens, então o tamanho do chunk do RAG não afeta a qualidade do resumo.

## Decisões

Escolhas registradas em 2026-10-30 pelo autor: **todas as recomendações**. A planilha `SPEC-018-decisoes-resumidor.xlsx` traz as opções descartadas e o motivo de cada recomendação.

| # | Questão | Escolha (2026-10-30) |
|---|---------|----------------------|
| A | Embeddings e chunks | Mantidos os 128 tokens (ADR 0004). A RN03 sai do escopo; o resumo usa uma divisão própria por seções |
| B | Disponibilidade | O resumidor está **sempre** no acesso rápido e o usuário não pode removê-lo |
| D1 | Vaga no acesso rápido | **Revista pelo autor em 2026-10-30, depois de ver a tela:** o resumidor é fixo, sempre o primeiro, e **ocupa uma das 4 vagas**. A tela inicial mostra no máximo 4 cartões; sobram 3 à escolha do usuário. `MAX_HOME_ASSISTANTS` continua 4 (escolha anterior: cartão fixo fora das 4 vagas) |
| D2 | Padrão | Padrão **só para quem nunca personalizou** o acesso rápido (`customized: false`). Quem personalizou mantém o padrão escolhido e pode marcar o resumidor como padrão |
| D3 | O que se altera | Não pode ser excluído (SPEC-014) nem ter nome, descrição ou prompt editados (SPEC-017). O administrador troca **só a credencial e o modelo** (SPEC-013). O prompt fica versionado no código |
| D4 | Quem vê | Todo usuário autenticado com papel no Nexus, sem passar por grupos |
| D5 | Nome | "Resumidor de documentos" |
| D6 | Quem vê o documento | Só quem enviou, e só na conversa em que enviou |
| D7 | Envio | Clipe no campo de mensagem mais arrastar e soltar, só com o resumidor ativo |
| D8 | Documentos por conversa | **1**. Outro documento exige "Nova conversa" |
| D9 | Retenção | O documento é apagado quando a conversa é excluída ou **30 dias** depois do envio, o que vier primeiro |
| D10 | O que se apaga ao expirar | Original, vetores e mini-resumos. A mensagem com o resumo já postada continua na conversa, que passa a mostrar "documento expirado" |
| D11 | Conversa arquivada | Arquivar não apaga nada; excluir apaga tudo |
| D12 | Auditoria | Eventos de envio, de resumo pronto e de exclusão ou expiração, com nome, tamanho e SHA-256, sem conteúdo |
| D13 | Teto em tokens | **40.000 tokens**, apresentado ao usuário como "cerca de 55 a 60 páginas de texto corrido" |
| D14 | Contagem | Tokenizador local do modelo de embeddings, que já está carregado. Determinística, independe do LLM |
| D15 | Acima do teto | **Rejeita**, mostrando a contagem e o limite |
| D16 | Tamanho do arquivo | 25 MB (o limite atual) |
| D17 | Formatos | `.txt`, `.md`, `.markdown`, `.pdf`, `.doc` e `.docx` (os de hoje) |
| D18 | PDF escaneado | Aceito com OCR e o mesmo teto, com aviso de que demora mais |
| D19 | Documento curto | Resumido mesmo assim, com uma única chamada |
| D20 | Limite de uso | **Cota própria de 10 documentos por dia por usuário**, separada das perguntas. O custo entra no total em USD do usuário |
| D21 | Ordem | Extrair → indexar (perguntas liberadas) → resumir |
| D22 | Seções | Pelos títulos detectados pelo parser, agrupados em lotes de **~6.000 tokens** (mínimo 4.000 e máximo 8.000) |
| D23 | Níveis | Dois níveis (mini-resumos e consolidado). Um terceiro nível entra automaticamente só se os mini-resumos passarem de 8.000 tokens |
| D24 | LLM | A credencial e o modelo do resumidor, com recuo para a credencial padrão (SPEC-013, D11) |
| D25 | Falha numa seção | 3 tentativas e depois o resumo falha por inteiro. As perguntas continuam funcionando |
| D26 | Estrutura | Modelo fixo: visão geral → pontos principais por seção → números, datas e prazos → conclusões ou próximos passos |
| D27 | Tamanho | Proporcional ao documento, de **300 a 1.000 palavras** |
| D28 | Idioma | Sempre pt-BR, avisando quando o original está em outro idioma |
| D29 | Citações | Cada ponto cita a seção de origem e, em PDF, a página, no formato `[n]` |
| D30 | O que se grava | Mini-resumos **e** consolidado, no PostgreSQL |
| D31 | Entrega | O resumo é **postado automaticamente** na conversa ao ficar pronto. O botão "Resumir" mostra de novo |
| D32 | Pedido por texto | Regra por palavras: pedido geral → resumo gravado; o resto vai para o RAG |
| D33 | Resumo sob medida | Pedido de resumo com recorte ("capítulo 3", "em 5 tópicos", "para um diretor") é montado a partir dos mini-resumos, em uma única chamada |
| D34 | Antes de ficar pronto | Mostra o progresso ("resumindo parte 4 de 9"). Perguntas já são aceitas se a indexação terminou |
| D35 | Parâmetros do RAG | Os padrões da SPEC-013 (híbrida, reranker, 30 candidatos, top 5, nota mínima 0,10), fixos no resumidor |
| D36 | Status visível | Enviado → extraindo → indexando → resumindo (x/y) → pronto, ou falhou com o motivo |
| D37 | "Para que sirvo" | Montado no servidor a partir das constantes, sem LLM |
| D38 | Quando aparece | Como boas-vindas ao abrir o resumidor numa conversa vazia, e em resposta a qualquer mensagem enviada sem documento |
| D39 | Mensagem sem documento | A mesma explicação mais um convite a anexar o arquivo. Sem chat livre com o LLM |
| D40 | Tabelas estruturadas (RN02) | **Fora**. Continua como limitação da PC-D7 |
| D41 | Comparar documentos | **Fora** |
| D42 | Avaliação automática do resumo | **Fora**. Entram um roteiro manual com 3 documentos fictícios e uma checagem de fidelidade por amostra (CT-152) |
| D43 | Baixar o resumo | **Fora**. Só o botão de copiar que as mensagens já têm |
| D44 | Paralelismo do resumo | **Até 4 chamadas ao LLM ao mesmo tempo** nos mini-resumos e nos grupos do terceiro nível; o consolidado vem depois de todos. Acrescentada em 2026-10-30: na medição do CT-151, 339 dos 355 s foram de 8 chamadas em sequência (cerca de 42 s cada) |

## Requisitos funcionais

- RF-112: existe exatamente um **assistente de sistema** "Resumidor de documentos" (D5), criado pela migração e visível a todo usuário autenticado com papel (D4). Ele não pode ser excluído e não tem nome, descrição, prompt nem parâmetros de recuperação editáveis. O administrador troca só a credencial e o modelo (D3).
- RF-113: o resumidor aparece **sempre** como o primeiro cartão do acesso rápido e ocupa uma das 4 vagas; o usuário escolhe os outros 3 (escolha B, D1 revista). É o padrão de quem nunca personalizou; quem personalizou pode escolhê-lo como padrão no modal, mas não pode desmarcá-lo do acesso rápido (D2).
- RF-114: com o resumidor ativo, o campo de mensagem mostra o clipe e aceita arrastar e soltar um arquivo (D7). O envio vale para a conversa atual, que é criada se ainda não existe. Uma conversa aceita **um** documento (D8). Com o documento já enviado, o clipe fica desabilitado e o aviso sugere "Nova conversa".
- RF-115: o envio responde em menos de 2 s com o documento no estado "enviado" e enfileira o processamento. A tela mostra as etapas da D36, inclusive "resumindo parte x de y", consultando o status a cada 3 s (SPEC-005).
- RF-116: o processamento extrai o texto, conta os tokens (D14), rejeita acima do teto (D15), indexa os trechos para o RAG e só então gera os mini-resumos por lote de seções e o resumo consolidado (D21 a D23). Mini-resumos e consolidado ficam gravados (D30).
- RF-117: quando o resumo fica pronto, ele é postado automaticamente na conversa como mensagem do assistente, com citações por seção e página (D29, D31). O botão "Resumir" mostra de novo o resumo gravado, sem chamar o LLM.
- RF-118: uma mensagem do usuário na conversa do resumidor segue a rota da RN-61: explicação da finalidade, resumo gravado, resumo sob medida a partir dos mini-resumos, ou pergunta pontual pelo RAG restrito ao documento da conversa.
- RF-119: sem documento na conversa, a abertura do resumidor mostra a mensagem de boas-vindas, e qualquer mensagem enviada recebe a mesma explicação (D37 a D39). A explicação traz a finalidade, os formatos aceitos, o tamanho máximo em MB, o teto em tokens com a equivalência aproximada em páginas, o tempo de retenção, a cota diária, a observação sobre PDF escaneado e o que fica fora (tabelas estruturadas e comparação de documentos).
- RF-120: o documento, os vetores, os mini-resumos e o original são apagados quando a conversa é excluída e, de qualquer forma, 30 dias depois do envio (D9 a D11). Na expiração, a conversa continua com as mensagens, mostra "documento expirado" e passa a responder com a explicação do RF-119, adaptada ("o documento desta conversa expirou").

## Requisitos não funcionais

- RNF-37: a entrega do resumo gravado (botão "Resumir" ou pedido geral por texto, D32) responde em **menos de 1 s no p95**, sem chamada ao LLM (RN06 do requisito de origem).
- RNF-38: a resposta "para que sirvo" responde em menos de 1 s no p95, sem chamada ao LLM (D37).
- RNF-39: o envio de um arquivo de 25 MB responde em menos de 2 s, sem timeout, e o processamento ocorre todo no worker (critério de aceite 1 do requisito de origem).
- RNF-40: um PDF de texto com cerca de 40.000 tokens chega a "pronto" em até **5 minutos** no ambiente de referência da V7, com o LLM padrão. É uma meta medida no CT-151, não um portão: a parte de indexação herda a limitação aceita do RNF-02 (PC-D11). Primeira medição (2026-10-30, `gemini-3.8-flash`, 37.799 tokens, 7 lotes): 355 s, dos quais 16 s de extração e indexação e 339 s de resumo em sequência; daí a D44.
- RNF-41: nenhum log, span, métrica ou evento de auditoria leva o texto do documento, dos mini-resumos ou do resumo (D12).

## Regras de negócio

- RN-55: o assistente de sistema é identificado por `assistants.system_kind = 'document_summarizer'`, único. As rotas de exclusão (SPEC-014), de edição de perfil (SPEC-017), de perfil de recuperação (SPEC-013) e de documentos da base (`/assistants/{id}/documents`) respondem **409 `system_assistant_readonly`** para ele. A rota de credencial e modelo continua só do administrador (SPEC-013, D7).
- RN-56: o resumidor é visível a todo usuário com papel no Nexus, sem grupo (D4). Ele **fica fora** do catálogo da inferência de assistente (`/assistants/infer`) e da seleção das 4 vagas do acesso rápido (D1).
- RN-57: acesso rápido efetivo = resumidor fixo no topo + até `MAX_HOME_ASSISTANTS - 1` (3) assistentes da RN-49 (SPEC-016), num total de 4 cartões. Uma seleção gravada com mais de 3 é recusada com `home_assistants_limit`. Se `customized: false`, o padrão é o resumidor. Se `customized: true`, o padrão é o gravado, e o resumidor pode ser esse padrão sem ocupar uma vaga. Nos dois casos, se o padrão gravado deixar de ser visível, o padrão efetivo passa a ser o resumidor (antes era o primeiro restante, D8 da SPEC-016).
- RN-58: um documento pessoal tem `owner_user_id` e `conversation_id` obrigatórios e pertence ao resumidor. Só o dono da conversa (`AccessPolicy.owns_conversation`, RN-24) envia, consulta status, lê o resumo e faz perguntas sobre ele. **Nem o administrador** lê o conteúdo (mesma regra das conversas). Uma conversa tem no máximo um documento pessoal; um segundo envio responde 409 `conversation_document_exists` (D8).
- RN-59: toda busca no Qdrant sobre documento pessoal aplica os filtros de sempre (`user_groups` e `active`), mais `owner_user_id` e `conversation_id` iguais aos da conversa. Os pontos pessoais gravam `allowed_groups` vazio, então o filtro de grupos não restringe nem amplia; a restrição real é a do dono e da conversa. Um teste garante que a falta desses dois filtros **impede** a busca (falha fechada), e não a abre.
- RN-60: limites do documento pessoal, todos como constantes do domínio em `domain/document_summary.py`:
  `MAX_SUMMARY_DOCUMENT_TOKENS = 40_000` (D13), contados pelo tokenizador local (D14), e `PAGES_PER_40K_TOKENS_HINT = "55 a 60"`, usado só no texto. Também `SUMMARY_DOCUMENT_RETENTION = 30 dias` (D9) e `DAILY_SUMMARY_DOCUMENTS = 10` (D20). O tamanho do arquivo e os formatos vêm do que já existe (`UPLOAD_MAX_BYTES` e a lista da ingestão, D16 e D17). A contagem acontece no worker, depois da extração: acima do teto, o documento vai para "falhou" com o motivo `document_too_long`, a contagem e o limite (D15), sem chamada ao LLM. A cota é verificada no envio, contando os documentos pessoais que o usuário enviou nas últimas 24 h, inclusive os que falharam ou foram apagados; acima dela a resposta é 429 `summary_daily_limit`.
- RN-61: roteamento da mensagem na conversa do resumidor, por função pura `route_summarizer_message(text, state)` (D32 a D34, D38, D39):
  1. sem documento, ou documento expirado → explicação da finalidade (RF-119), sem LLM e sem consumir cota;
  2. documento em processamento antes de indexar → mensagem de progresso com a etapa atual, sem LLM;
  3. pedido de resumo **geral** → resumo gravado, ou, se ainda não está pronto, o progresso "resumindo parte x de y";
  4. pedido de resumo **com recorte** → resumo sob medida, com uma chamada ao LLM sobre os mini-resumos (D33). Se os mini-resumos ainda não estão prontos, responde com o progresso;
  5. qualquer outra mensagem → pergunta pontual pelo RAG (D35), restrita pela RN-59.
  "Pedido de resumo" é a mensagem que contém um termo da família "resum-" ou "sintetiz-", ou as expressões "visão geral" ou "principais pontos". O pedido é **geral** quando, sem esses termos, sobram só palavras de ligação ou referências ao documento ("o", "documento", "arquivo", "texto", "por favor", "me", "faça", "um", "dê"...). Se sobra outro conteúdo, o pedido é **com recorte**. A lista fechada de termos e palavras fica no domínio, coberta por exemplos no CT-139.
- RN-62: o resumo consolidado e o sob medida seguem o modelo da D26, em pt-BR (D28), com 300 a 1.000 palavras proporcionais ao documento (D27): `palavras_alvo = clamp(300, 1000, tokens_do_documento / 40)`. Cada ponto cita `[n]`, em que `n` aponta para a seção (título e, em PDF, a página inicial) de onde veio (D29). Quando o idioma detectado do original não é português, o resumo começa avisando o idioma original.
- RN-63: lotes de seção (D22): seções do parser na ordem do documento, agrupadas até ~6.000 tokens. Uma seção maior que 8.000 tokens é dividida por parágrafos. Um lote final menor que 4.000 tokens é juntado ao anterior, se a soma não passar de 8.000. Um documento abaixo de 4.000 tokens é um lote único e gera o resumo em uma chamada (D19), que vale ao mesmo tempo como mini-resumo e como consolidado. Se a soma dos mini-resumos passar de 8.000 tokens, eles são consolidados em grupos antes do consolidado final (D23). Os mini-resumos de um nível rodam em paralelo, no máximo `SUMMARY_PARALLEL_CALLS = 4` ao mesmo tempo (D44); cada um é gravado assim que fica pronto, e uma falha num lote não descarta os que já terminaram (a nova tentativa refaz só os que faltam).
- RN-64: falha (D25). Cada chamada ao LLM tem as 3 tentativas da ingestão. Se uma esgotar, o **resumo** vai para "falhou" com o motivo, mas a **indexação** continua "pronta" e as perguntas pelo RAG continuam funcionando. O botão "Tentar resumir de novo" reenfileira só o resumo, sem reindexar e sem consumir outra cota.
- RN-65: o uso do LLM no resumo é gravado em `usage_records` com `operation = 'document_summary'`, `conversation_id` e custo estimado. Esses registros **não contam** nos limites de 20 perguntas por minuto e 500 por dia (D20), mas entram nos relatórios de custo por usuário. As perguntas pontuais e os resumos sob medida são `operation = 'chat'` e contam como perguntas.
- RN-66: o prompt de sistema do mini-resumo, do consolidado e do resumo sob medida fica em `application/services/document_summary_prompts.py`, com `SUMMARY_PROMPT_VERSION`, que é gravada com cada resumo (D3). O conteúdo do documento vai **sempre** delimitado como dado, nunca como instrução, e passa pela mesma checagem de injeção de prompt das perguntas (`domain/prompt_injection.py`).
- RN-67: auditoria (D12) com os eventos `summary_document.uploaded` (nome, tamanho, SHA-256, formato, `conversation_id`), `summary_document.summarized` (tokens, número de lotes, duração e modelo) e `summary_document.deleted` (motivo `conversation_deleted` ou `expired`). Nenhum evento leva conteúdo.

## Critérios de aceite

```gherkin
Cenário: resumidor disponível sem nenhum assistente criado (RF-112, RF-113, RN-57)
  Dado um usuário comum sem acesso a nenhum assistente da organização
  Quando ele abre o Nexus
  Então o acesso rápido mostra o cartão "Resumidor de documentos" marcado como padrão
  E a conversa vazia mostra a mensagem de boas-vindas com formatos, 25 MB, 40.000 tokens
    (cerca de 55 a 60 páginas), 30 dias de retenção e 10 documentos por dia

Cenário: pergunta sem documento (RF-119, RN-61 item 1)
  Dado o resumidor ativo numa conversa sem documento
  Quando o usuário pergunta "quais arquivos você aceita?"
  Então a resposta é a explicação da finalidade, em menos de 1 s
  E nenhuma chamada ao LLM é feita e nenhuma cota é consumida

Cenário: cartão fixo e padrão escolhido (RN-57, D1, D2)
  Dado um usuário que personalizou o acesso rápido com 3 assistentes e o "Jurídico" como padrão
  Então a tela inicial mostra o resumidor primeiro, mais 3 escolhidos (4 cartões)
  E o "Jurídico" está marcado como padrão
  E o modal "Personalizar acesso rápido" mostra o resumidor sem a opção de desmarcar

Cenário: assistente de sistema protegido (RN-55)
  Quando o administrador tenta excluir o resumidor, editar o prompt dele ou enviar documento para a base dele
  Então a API responde 409 "system_assistant_readonly"
  E a troca de credencial e modelo do resumidor pelo administrador responde 200

Cenário: envio e resumo automático (RF-114 a RF-117)
  Dado o resumidor ativo
  Quando o usuário anexa um PDF fictício de 30 páginas
  Então o envio responde em menos de 2 s com o estado "enviado"
  E a tela mostra "extraindo", "indexando" e "resumindo parte x de y"
  E ao terminar o resumo aparece na conversa com visão geral, pontos por seção,
    números e prazos, conclusões e citações [n] com seção e página

Cenário: entrega instantânea (RNF-37, D31, D32)
  Dado um documento com resumo pronto
  Quando o usuário clica em "Resumir" ou escreve "resuma o documento"
  Então o mesmo resumo gravado é exibido em menos de 1 s, sem chamada ao LLM

Cenário: resumo sob medida (RN-61 item 4, D33)
  Quando o usuário escreve "resuma em 5 tópicos para um diretor"
  Então a resposta vem de uma única chamada ao LLM sobre os mini-resumos
  E nenhum trecho do RAG é recuperado

Cenário: pergunta pontual (RN-61 item 5, RN-59)
  Quando o usuário pergunta "qual o prazo de vigência?"
  Então a resposta usa no máximo 5 trechos do documento da própria conversa, com citações
  E a busca tem os filtros user_groups, active, owner_user_id e conversation_id

Cenário: documento acima do teto (RN-60, D15)
  Quando o usuário envia um DOCX fictício de 52.000 tokens
  Então o documento vai para "falhou" com a mensagem "O documento tem 52.000 tokens; o limite é 40.000"
  E nenhuma chamada ao LLM é feita

Cenário: segundo documento na conversa (RN-58, D8)
  Dado uma conversa que já tem um documento
  Quando o usuário tenta anexar outro
  Então a API responde 409 "conversation_document_exists"
  E a tela sugere "Nova conversa"

Cenário: cota diária (RN-60, D20)
  Dado um usuário que já enviou 10 documentos nas últimas 24 h
  Quando ele envia o 11º
  Então a API responde 429 "summary_daily_limit"
  E as perguntas pelo chat continuam no limite de 20 por minuto e 500 por dia

Cenário: isolamento entre usuários (RN-58, RN-59)
  Dado que a usuária A enviou um documento na conversa dela
  Quando o usuário B, ou o administrador, consulta status, resumo ou faz perguntas nessa conversa
  Então a API responde 404
  E nenhuma busca de B no resumidor devolve trecho do documento de A

Cenário: falha no resumo com perguntas preservadas (RN-64, D25)
  Dado que o LLM falha 3 vezes num lote
  Então o resumo fica "falhou" com o motivo e o botão "Tentar resumir de novo"
  E as perguntas pontuais continuam respondidas pelo RAG

Cenário: expiração e exclusão (RF-120, D9 a D11)
  Dado um documento enviado há 30 dias
  Quando o worker roda a limpeza
  Então o original, os vetores e os mini-resumos são apagados e o evento "summary_document.deleted" é gravado
  E a mensagem do resumo continua na conversa, que mostra "documento expirado"
  E excluir a conversa apaga tudo imediatamente; arquivar não apaga nada
```

## Design da solução

### Domínio

- `domain/document_summary.py` (sem framework):
  - constantes da RN-60, `SUMMARY_BATCH_TARGET_TOKENS = 6_000`, `SUMMARY_BATCH_MIN_TOKENS = 4_000` e `SUMMARY_BATCH_MAX_TOKENS = 8_000` (D22);
  - `SummaryStage` (`enviado`, `extraindo`, `indexando`, `resumindo`, `pronto`, `falhou`, `expirado`) e `SummaryProgress(stage, done, total, failure_code)`;
  - `plan_summary_batches(sections: Sequence[SectionTokens]) -> tuple[SummaryBatch, ...]` (RN-63), uma função pura;
  - `target_summary_words(document_tokens: int) -> int` (RN-62);
  - `route_summarizer_message(text, state) -> SummarizerRoute` e os vocabulários fechados (RN-61);
  - `summarizer_capabilities(upload_max_bytes, formats) -> SummarizerCapabilities`, a fonte única do texto do RF-119 (D37).
- `domain/entities.py`: `Assistant.system_kind: str | None`; `Document.owner_user_id`, `Document.conversation_id` e `Document.expires_at` (todos `None` nos documentos da base); `DocumentSummary` e `DocumentSummarySection`.
- `domain/access.py`: `AccessPolicy.can_access_assistant` aceita o assistente de sistema para todo usuário com papel (RN-56); `can_use_personal_document(user, conversation_owner)` repete a RN-24 (RN-58).
- `domain/home_assistants.py`: `effective_home_assistants` recebe `pinned_id` e aplica a RN-57; `HomeAssistantSelection` recusa o resumidor nas vagas com `code` `home_assistant_pinned`.
- `domain/interfaces.py`, portas novas: `TokenCounter.count(text) -> int` (D14) e `DocumentSummaryRepository` (gravar e ler o consolidado e os mini-resumos, gravar o progresso, apagar por documento e listar os vencidos).
- `AuditAction`: os três eventos da RN-67.

### Aplicação

- `application/use_cases/summary_documents.py`:
  - `UploadSummaryDocumentUseCase`: confere a RN-58 (dono, conversa do resumidor, nenhum documento), confere a cota (RN-60), grava o original pelo armazenamento atual, cria o `Document` pessoal com `expires_at`, enfileira o job `kind='ingest'` e audita.
  - `GetSummaryDocumentStatusUseCase`: devolve `SummaryProgress` (RF-115).
  - `GetStoredSummaryUseCase`: lê o consolidado do repositório (RNF-37).
  - `RetrySummaryUseCase`: reenfileira `kind='resumo'` (RN-64).
  - `PurgeExpiredSummaryDocumentsUseCase`: apaga vetores → original → mini-resumos e documento, e audita (RF-120). A mensagem postada não é apagada.
- `process_ingestion.py`: no fim de uma ingestão bem-sucedida de documento pessoal, conta os tokens (RN-60) **antes** dos embeddings. Acima do teto, falha definitiva `document_too_long`. Caso contrário, indexa com payload `owner_user_id` e `conversation_id` e enfileira `kind='resumo'` (D21).
- `application/services/document_summary.py`: `HierarchicalSummarizer`, que usa o `LLMGateway` existente com a credencial do resumidor e recuo (D24), aplica a RN-63, grava cada mini-resumo e o progresso, consolida, monta as citações (D29), grava o consolidado com `SUMMARY_PROMPT_VERSION` e posta a mensagem na conversa (D31). Também `tailored_summary(request, sections)` para a D33.
- `chat_with_assistant.py`: quando o assistente é o resumidor, aplica `route_summarizer_message` **antes** do grafo do LangGraph. As rotas 1 a 3 respondem sem LLM e sem registro de uso. A rota 4 chama `tailored_summary`. A rota 5 segue o grafo atual com o `payload_filter` da RN-59 e o perfil fixo da D35.
- `ManageConversationUseCase.delete`: apaga o documento pessoal da conversa antes de apagar a conversa (RF-120), com o mesmo caminho da limpeza.
- `ListAssistantsUseCase` e `InferAssistantUseCase`: o resumidor entra na lista e fica fora do catálogo da inferência (RN-56). `AssistantDTO.is_system`.
- `DeleteAssistantUseCase`, `UpdateAssistantUseCase`, `ConfigureAssistantUseCase` (perfil de recuperação) e o envio para a base: levantam `SystemAssistantReadonlyError` (RN-55).
- `cli/worker.py`: trata `kind='resumo'` e roda `PurgeExpiredSummaryDocumentsUseCase` a cada hora.

### Infraestrutura

- `TokenCounter` com o tokenizador de `sentence_transformer_embedding.py`, sem truncamento. Usa o `MODEL_LOAD_LOCK` e a trava por modelo que já existem.
- `PostgresDocumentSummaryRepository`.
- `QdrantVectorStoreGateway`: índices de payload `owner_user_id` e `conversation_id`; `_filter` passa a **exigir** os dois quando a collection é a do resumidor (RN-59, falha fechada).

### API

| Método | Rota | Corpo / resposta | Erros |
|--------|------|------------------|-------|
| GET | `/summarizer` | `{assistant_id, capabilities: {formats, max_bytes, max_tokens, pages_hint, retention_days, daily_limit, scanned_pdf_note, out_of_scope}, welcome_markdown}` (D37) | 401 |
| POST | `/conversations/{id}/document` | multipart `file`; 202 com `SummaryDocumentResponse` | 401; 404 conversa; 409 `conversation_document_exists`, `not_summarizer_conversation`; 413; 415; 429 `summary_daily_limit` |
| GET | `/conversations/{id}/document` | `{document_id, source_name, stage, done, total, failure_code, failure_detail, expires_at}` | 401; 404 |
| GET | `/conversations/{id}/summary` | `{content, citations, prompt_version, created_at}` | 401; 404; 409 `summary_not_ready` |
| POST | `/conversations/{id}/summary/retry` | 202 | 401; 404; 409 `summary_not_failed` |
| PUT/DELETE | rotas existentes do assistente | — | 409 `system_assistant_readonly` (RN-55) |

`404` em conversa alheia, nunca `403`, para não revelar que a conversa existe (RN-24). Os códigos novos ficam em `api/error_codes.py`.

### Persistência (migração `0013_document_summarizer`)

- `assistants.system_kind varchar(32) NULL`, com índice único parcial `WHERE system_kind IS NOT NULL`. O `INSERT` do resumidor (id fixo, sem grupo, `llm_credential_id` nulo para seguir a padrão) é idempotente.
- `documents`: `owner_user_id varchar(128) NULL`, `conversation_id varchar(64) NULL FK conversations.id ON DELETE SET NULL` e `expires_at timestamptz NULL`. A check constraint de status passa a incluir `'expirado'`. Índices `(conversation_id)` e `(owner_user_id, created_at)` (cota). Mais um check: `conversation_id IS NULL OR owner_user_id IS NOT NULL` (conversa só com dono). Depois da exclusão da conversa ou da expiração, a linha fica como lápide com status `expirado`, sem conteúdo, e sustenta a cota e a auditoria (ADR 0014, item 6; T7 do plano).
- `ingestion_jobs.kind` passa a aceitar `'resumo'`.
- `document_summaries` com `document_id PK FK documents ON DELETE CASCADE`, `stage`, `batches_done`, `batches_total`, `content text NULL`, `citations jsonb NULL`, `document_tokens int`, `prompt_version varchar(16)`, `model varchar(200)`, `failure_code varchar(64) NULL` e `created_at`/`updated_at`.
- `document_summary_sections` com `document_id FK ON DELETE CASCADE`, `position smallint`, `title text`, `page_start int NULL`, `input_tokens int`, `content text`. Chave primária `(document_id, position)`.
- `usage_records.operation varchar(32) NOT NULL DEFAULT 'chat'`, em que o padrão preenche as linhas antigas (RN-65). A contagem dos limites filtra `operation = 'chat'`.

Pelo `/new-migration`; nenhuma migração existente é editada.

### Frontend

- `nexus-api.service.ts`: `getSummarizer`, `uploadConversationDocument`, `getConversationDocument`, `getStoredSummary` e `retrySummary`.
- Store `nexus`: o estado `summarizer` (capacidades) e `conversationDocument` por conversa, com polling de 3 s enquanto não está `pronto`, `falhou` ou `expirado`. Ao chegar em `pronto`, recarrega as mensagens da conversa (D31).
- Composer: clipe e área de soltar visíveis só com o resumidor ativo (D7); validação local de formato e tamanho com as capacidades do servidor; chip do documento com a etapa e o progresso (D36), "Resumir" (D31) e "Tentar resumir de novo" (RN-64).
- Conversa vazia com o resumidor: mensagem de boas-vindas renderizada de `welcome_markdown`, sem gravar (D38).
- Acesso rápido: cartão fixo do resumidor primeiro, com selo "Sistema"; no modal ele aparece sem caixa de marcação, mas com o botão de padrão (RN-57). Página `/assistants`: o resumidor mostra só o card de LLM ao administrador (D3), sem lixeira (SPEC-014).
- Regras puras em `shared/summarizer/summarizer.ts` (texto das etapas, validação local e rótulos de erro), com testes no Vitest.

## Impacto arquitetural

- **ADR 0014 — "Documento pessoal e assistente de sistema"** (aceita em 2026-10-30): registra a exceção ao modelo da ADR 0008, em que só administrador e curador enviam documentos. Também registra o isolamento por dono e conversa dentro de uma única collection `assistant_{resumidor}` (compatível com a ADR 0003), o filtro de falha fechada (RN-59) e a retenção de 30 dias.
- A ADR 0004 continua: embeddings locais de 128 tokens. **O texto do documento vai ao LLM externo no resumo**, como já acontece com os trechos recuperados numa pergunta. A ADR 0014 registra isso e a explicação do RF-119 avisa o usuário.
- A ADR 0009 (ingestão assíncrona) ganha o job `resumo` na mesma fila, sem infraestrutura nova.
- A SPEC-016 muda: RN-49 e D8 (padrão efetivo) passam a considerar o cartão fixo (RN-57). A SPEC-014 e a SPEC-017 ganham a exceção da RN-55. A matriz de permissões da SPEC-004 ganha "enviar documento pessoal: todo usuário com papel, só na própria conversa".
- `CLAUDE.md`: a regra "toda busca no Qdrant filtra `user_groups` e `active`" continua valendo e ganha o complemento da RN-59.
- Sem dependência nova: tokenizador, extração, OCR, LLM e fila já existem.

## Estratégia de testes

| ID | Tipo | O que cobre | Requisitos |
|----|------|-------------|------------|
| CT-139 | Unitário | `route_summarizer_message` com tabela de exemplos: sem documento, em processamento, geral ("resuma", "resumo do documento, por favor"), com recorte ("resuma o capítulo 3", "em 5 tópicos"), pergunta comum, expirado | RN-61 |
| CT-140 | Unitário | `plan_summary_batches`: 1 seção curta, seções somando 6 mil, seção de 12 mil dividida, último lote pequeno juntado, limite 8 mil respeitado; `target_summary_words` em 2 mil, 12 mil e 40 mil tokens | RN-62, RN-63 |
| CT-141 | Unitário | `effective_home_assistants` com cartão fixo: sem personalização, com padrão escolhido, resumidor como padrão, padrão perdido → resumidor; seleção com o resumidor nas vagas → `home_assistant_pinned` | RN-57 |
| CT-142 | Unitário | `AccessPolicy` e casos de uso: resumidor visível a todo papel; 409 em exclusão, edição de perfil, perfil de recuperação e envio para a base; credencial liberada ao admin | RN-55, RN-56 |
| CT-143 | Unitário | `UploadSummaryDocumentUseCase`: dono, conversa de outro assistente, segundo documento, cota 10/11 com documentos falhos e apagados contando, auditoria sem conteúdo | RN-58, RN-60, RN-67 |
| CT-144 | Unitário | Ingestão pessoal com dublês: teto 40.000/40.001 → `document_too_long` sem LLM; payload com dono e conversa; job `resumo` só depois de indexar | RN-60, D21 |
| CT-145 | Unitário | `HierarchicalSummarizer` com LLM falso: progresso x/y, terceiro nível acima de 8 mil, falha após 3 tentativas mantém a indexação, nova tentativa sem nova cota, `prompt_version` gravada, documento delimitado como dado, uso com `operation='document_summary'`; no máximo 4 chamadas simultâneas e lote falho sem perder os prontos (D44) | RN-62 a RN-66, D44 |
| CT-146 | Unitário | `summarizer_capabilities`: o texto traz exatamente os valores das constantes e de `UPLOAD_MAX_BYTES`; mudar uma constante muda o texto | RF-119, D37 |
| CT-147 | Integração | Rotas novas: 202, 401, 404 em conversa alheia (inclusive de admin), 409, 413, 415, 429; `GET /summary` 409 antes de pronto; chat sem documento sem registro de uso | RF-114 a RF-119, RN-58 |
| CT-148 | Integração (Docker) | Qdrant real: busca de B nunca devolve ponto de A; filtro sem `owner_user_id` falha fechado; `active` e `user_groups` presentes | RN-59 |
| CT-149 | Integração (Docker) | Migração `0013` sobre a base da rc9: resumidor criado uma vez (rodar duas vezes), checks novos, `usage_records` antigos como `chat`, limites de perguntas ignoram `document_summary`; exclusão da conversa e limpeza de expirados apagam vetores, original e seções e mantêm a mensagem | RF-120, RN-65 |
| CT-150 | Vitest | Regras puras do resumidor, reducer e effects (polling até estado final, recarga de mensagens em `pronto`), composer (clipe só com o resumidor, recusa local de formato e tamanho), cartão fixo e modal | RF-113 a RF-115 |
| CT-151 | E2E (Playwright) + medição | Usuário sem assistente vê o resumidor e as boas-vindas; envia um PDF fictício (cerca de 40 mil tokens); acompanha as etapas; recebe o resumo automático; "Resumir" < 1 s; pergunta pontual com citação; tempo total registrado (RNF-40) | RF-112 a RF-118, RNF-37 a RNF-40 |
| CT-152 | Manual | 3 documentos fictícios (um contrato em DOCX, um relatório em PDF com OCR e uma ata em TXT): estrutura da D26, idioma, citações conferidas por amostra (5 afirmações por resumo contra a seção citada), tela a 360 px e 1280 px, teclado | RN-62, D42 |

## Riscos e dependências

| Risco | Mitigação |
|-------|-----------|
| Vazamento de documento pessoal entre usuários | Filtro de falha fechada (RN-59), 404 em conversa alheia (RN-58), CT-148 com Qdrant real e revisão pelo subagente `architecture-guard` antes do PR |
| O texto do documento vai ao LLM externo | Mesmo fluxo de dados das perguntas (os trechos já vão), registrado na ADR 0014 e avisado ao usuário no RF-119. O provedor é o da credencial do resumidor (D24) |
| Injeção de prompt dentro do documento | O documento entra delimitado como dado, com a checagem existente (RN-66), e o modelo de saída é fixo (D26) |
| Custo por documento (de 6 a 11 chamadas ao LLM) | Cota de 10 por dia (D20), teto de 40 mil tokens, `operation` separada nos relatórios de custo (RN-65) |
| Processamento demorado em CPU, sobretudo com OCR | Etapas visíveis (D36), perguntas liberadas depois da indexação (D21), meta medida, não portão (RNF-40) |
| A contagem pelo tokenizador local difere da do LLM | É um teto de produto, não o limite do modelo: os lotes de até 8 mil tokens ficam bem abaixo do contexto dos modelos suportados. O CT-145 registra a razão entre as duas contagens no LLM falso; o CT-151 mede no real |
| Resumo infiel | Citações por seção (D29), roteiro com checagem por amostra (CT-152) e `prompt_version` gravada, para comparar versões. A avaliação automática fica para outra SPEC (D42) |
| A mudança no padrão efetivo da SPEC-016 surpreende quem tinha um padrão que perdeu o acesso | Antes caía para o primeiro restante, agora cai para o resumidor. O CT-141 cobre, e a nota de versão registra a mudança |
| A palavra "resumo" dentro de uma pergunta comum desvia para o caminho de resumo | Vocabulário fechado e exemplos no CT-139; o caminho com recorte (D33) responde a partir dos mini-resumos, o que continua útil |

## Rastreabilidade do requisito de origem

| Item de origem | Como fica nesta SPEC |
|----------------|----------------------|
| RN01 (fila assíncrona, teto de 40 mil tokens, aviso acima) | RF-115, RN-60, D13 a D15. Vale para os 6 formatos (D17), não só PDF. A equivalência fica em "55 a 60 páginas", não 80 |
| RN02 (estrutura e tabelas) | Títulos e seções preservados pelo parser atual (D22). Tabelas estruturadas **fora** (D40, PC-D7) |
| RN03 (chunks de 500 a 1.000 tokens, sobreposição de 100 a 200) | **Fora** (escolha A). O RAG continua com 128 tokens; o resumo usa lotes de 4 a 8 mil tokens (RN-63) |
| RN04 (mini-resumos e resumo hierárquico) | RF-116, RN-63, D22 e D23 |
| RN05 (resumo gravado no banco por `document_id`) | `document_summaries` e `document_summary_sections`, D30 |
| RN06 (resumo em menos de 1 s; RAG com top-K de 3 a 5) | RNF-37, RN-61 e D35 (top 5) |
| Critério 1 (sem timeout, status na tela) | RNF-39, RF-115, CT-151 |
| Critério 2 (tabelas e cabeçalhos legíveis) | Só os cabeçalhos; as tabelas ficam fora (D40) |
| Critério 3 (chunking de 500 a 1.000) | Fora (escolha A) |
| Critério 4 (resumo gravado e entregue ao clicar) | RF-117 e RNF-37. **Mudou com a D31**: o resumo também é postado automaticamente |
| Critério 5 (perguntas sem o documento inteiro na memória) | RN-61 item 5 com top 5 (D35) |

## Decisões pendentes

Nenhuma de escopo: D1 a D43 escolhidas em 2026-10-30. Para a revisão do texto:

1. A lista fechada de termos e palavras de ligação da RN-61 entra por exemplos no CT-139. Se o autor quiser outros termos ("sumarize", "TL;DR"), eles entram na revisão.
2. O texto final das boas-vindas (RF-119) sai das constantes. O plano traz uma primeira versão para o autor ajustar a redação, sem mudar os números.
