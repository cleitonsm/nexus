# SPEC-012 — Dispositivos normativos na recuperação e formato da resposta

**ID**: SPEC-20261026-012
**Status**: **Implementada** em 2026-10-27 — validada no Docker pelo autor (CT-91 a CT-98; linha de base oficial do `normativo-ficticio`). Histórico: Aprovada em 2026-10-26 por Cleiton Medeiros (D1 a D10; D9 revista para 0,10 e D14 acrescentada na validação). D11 a D13 ficam para uma SPEC de continuação.
**Origem**: teste com um assistente jurídico com a Constituição Federal indexada. A pergunta
"Explique o artigo 5 da constituição" caiu no fallback. Logs de 2026-10-26 (21:21 a 21:29 UTC):
`top_score` entre 0,09 e 0,14 nas três perguntas; numa delas nenhum trecho passou da nota
mínima, e nas outras o trecho aprovado não tratava do Art. 5º e a resposta foi recusada por falta
de citação válida.
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

1. **A busca esparsa não casa a referência.** A normalização do BM25 (NFKD) transforma `º` em
   `o`: o documento gera os termos `art`, `5o`, e a pergunta gera `artigo`, `5`. Nenhum termo
   coincide; a busca exata, que deveria resolver perguntas por número de dispositivo, não
   contribui.
2. **A estrutura do texto normativo se perde.** A heurística de títulos em PDF (D2 da SPEC-002)
   só reconhece títulos numerados ("1 Introdução"). "TÍTULO II", "CAPÍTULO I", "Seção II" e
   "Art. 5º" viram parágrafos comuns, então os trechos não levam no prefixo a que artigo
   pertencem.
3. **Um artigo longo vira dezenas de trechos.** O limite do modelo de embedding (128 tokens) divide
   o Art. 5º (78 incisos e 4 parágrafos) em dezenas de trechos, e só o primeiro contém "Art. 5º".
   O inciso XI não tem nada que o ligue ao artigo.
4. **A pergunta tem pouco conteúdo semântico.** "Explique o artigo 5" não descreve o assunto; o
   reranker dá nota baixa a todos os candidatos.
5. **Mesmo achando o artigo, a resposta não caberia.** O contexto leva no máximo `RERANK_TOP_N`
   (5) trechos dentro de `CONTEXT_TOKEN_BUDGET` (2.000 tokens). O Art. 5º tem, por estimativa, entre
   10 e 14 mil tokens, contando os prefixos dos trechos.
6. **Não há regra de formato.** A instrução padrão só pede objetividade. Não há orientação para
   respostas longas nem para conteúdo enumerado (incisos, alíneas, listas de requisitos).

## Objetivo

- Perguntas que citam um dispositivo ("art. 5º", "artigo 5", "inciso XI do art. 5º", "§ 2º do
  art. 7") recuperam o dispositivo inteiro, em ordem, do documento certo.
- Respostas são sucintas por padrão. Quando o conteúdo é enumerado, todos os itens aparecem,
  seguidos de um resumo explicativo.
- Nenhuma regressão nos conjuntos de avaliação atuais (`nexus-docs`, `nexus-docs-ampliado`).

## Decisões

Escolhidas por Cleiton Medeiros em 2026-10-26, antes do código.

| # | Tema | Escolha | Alternativas descartadas |
|---|------|------------------------|--------------|
| D1 | Formato de enumerações longas | **(a)** Todos os itens, cada um numa linha resumida com citação `[n]`, seguidos de um resumo explicativo de até 5 frases. | (b) Todos os itens com o texto integral, seguidos do resumo: resposta muito longa e lenta. (c) Resumo agrupado por tema, com a lista completa só quando o usuário pedir. |
| D2 | Onde fica a regra de formato | Instrução **global** no sistema, junto da regra de citação (`build_answer_instruction`), valendo para todos os assistentes. O prompt inicial do assistente continua antes dela e pode detalhar o tom. | Só no prompt inicial de cada assistente: não resolve os assistentes existentes. |
| D3 | Quando reconhecer estrutura normativa | **Automaticamente**, por documento: o extrator ativa o modo normativo quando encontra pelo menos **5 linhas** que começam com `Art. <número>`. Abaixo disso, nada muda (um manual que cita "art. 7" não é afetado). | (b) Marcação manual "documento normativo" no envio: exige mudança de tela e de esquema e falha se o curador esquecer. |
| D4 | Níveis da estrutura | `TÍTULO` → 1, `CAPÍTULO` → 2, `Seção` → 3, `Subseção` → 4, `Art. N` → 5 (com ou sem `º`, `o`, `-A`). Incisos, parágrafos e alíneas continuam no corpo do artigo. Vale para PDF, DOCX e texto. Se o prefixo não couber no limite (`CHUNK_PREFIX_MAX_TOKENS`, 32), saem primeiro os níveis externos, como hoje: o `Art. 5º` sempre fica. | Tratar parágrafos e incisos como subníveis: prefixos longos e trechos menores sem ganho para a pergunta por artigo. |
| D5 | Normalização da busca esparsa | Na indexação e na pergunta: ordinais `5º`, `5o`, `5ª` → `5`; `artigo`/`artigos`/`art` → `art`; `parágrafo`/`§` → `par`; `inciso`, `alínea` mantidos. Muda a tokenização: sobe `PIPELINE_VERSION` para `4` e exige reindexar. | Só normalizar a pergunta: não funciona, o documento indexado já tem `5o`. |
| D6 | Busca por referência | Quando a pergunta cita um artigo e a base tem trechos marcados com ele, o contexto passa a ser **o artigo inteiro em ordem** (`chunk_index`), lido do Qdrant com os mesmos filtros de `user_groups` e `active`. A nota mínima não se aplica a esse caminho (a correspondência é exata). Pergunta sobre um inciso ou parágrafo específico: lê o artigo, o reranker escolhe os trechos, e o trecho com o `caput` entra sempre. Sem trecho marcado, segue a busca híbrida atual. | Só reforçar a busca híbrida com o prefixo: melhora, mas não garante o artigo inteiro nem a ordem. |
| D7 | Artigo presente em mais de um documento | Usa o documento que aparece primeiro nos candidatos da busca híbrida da mesma pergunta; se nenhum aparecer, o documento cujo nome tem mais termos em comum com a pergunta ("constituição"); se empatar, todos, por ordem de nome, até o orçamento. A resposta cita a fonte de cada trecho, como hoje. | Pedir ao usuário que escolha o documento: exige mudança na tela e no fluxo do chat. |
| D8 | Orçamento do contexto estrutural | Nova variável `STRUCTURAL_CONTEXT_TOKEN_BUDGET`, padrão **16.000** tokens (contados pelo tokenizador do embedding, como os demais orçamentos). Se o dispositivo não couber, entram os primeiros trechos e a resposta diz quais itens ficaram de fora ("os incisos LXX a LXXVIII não couberam"). Nunca corta em silêncio. | Resumir em etapas (map-reduce): mais chamadas ao LLM, custo e latência maiores; fica como evolução. |
| D9 | Nota mínima (`RELEVANCE_MIN_SCORE`) | **0,10, o valor calibrado no CT-22** (revista pelo autor em 2026-10-27). A escolha inicial (0,30 já) foi medida na validação: no `nexus-docs-ampliado` a recuperação ficou igual (recall@5 0,984, MRR 0,901), mas 6 perguntas do escopo passaram a cair no fallback (respostas com citação 0,935 → 0,839) e a recusa das fora do escopo ficou em 0,90; pela calibração de 2026-10-20, 4 dessas perguntas têm nota entre 0,11 e 0,22. O caminho estrutural (D6) não usa a nota mínima. | 0,30: tirou respostas boas sem ganho na recusa; recalibrar antes de decidir. |
| D10 | Dados de teste | Testes unitários e conjunto de avaliação `normativo-ficticio.jsonl` sobre um **regulamento fictício** com a mesma estrutura (títulos, capítulos, artigos com incisos e parágrafos), seguindo a regra de dados fictícios do projeto. A Constituição entra só na validação manual, no ambiente do autor. | Usar a Constituição no conjunto versionado: é texto público, mas foge da regra de dados fictícios. |
| D14 | Tempo limite das chamadas ao LLM | (2026-10-27, decidida pelo autor) Nova variável `LLM_TIMEOUT_SECONDS` para o chat e a avaliação; padrão 30 s (sem mudança para quem não configurar), `.env.example` com 120 s. O teste da chave na administração mantém 15 s. Achado na validação: com o Art. 5º inteiro (50 trechos, ~41 KB de requisição) o `gemini-3.8-flash` não começou a responder em 30 s (`llm.request.timeout`). | 30 s fixo; tempo maior só no caminho estrutural; reduzir o orçamento do contexto. |

### Pendentes (achados da revisão do pipeline em 2026-10-26)

| # | Tema | Opções | Situação |
|---|------|--------|----------|
| D11 | Pergunta cita um artigo de norma que **não** está na base, mas outra norma da base tem o mesmo número ("art. 5 do CDC" numa base só com a Constituição) | (a) Aviso no sistema ao LLM com os nomes dos documentos lidos: se a norma pedida for outra, responder que ela não está na base; sem citação, vale o fallback (RN-18). (b) Exigir que alguma palavra do nome da norma na pergunta apareça no nome do arquivo; senão, busca híbrida e nota mínima (falha se o arquivo tiver nome diferente, como `CF88.pdf`). (c) Manter como está e registrar o risco. | Aberta. Hoje vale (c). |
| D12 | Texto revogado ou tachado (PDF do Planalto traz a redação antiga e a nova do mesmo artigo) | (a) Orientar o curador a enviar a versão compilada sem texto revogado. (b) Descartar na extração linhas marcadas "(Revogado)" e redações substituídas. (c) Instrução ao LLM para preferir a redação em vigor. | Aberta; medir no CT-98. |
| D13 | ADCT da Constituição reinicia a numeração ("Art. 5º" de novo) | (a) Reconhecer "ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS" (e "DISPOSIÇÕES TRANSITÓRIAS") como nível 1. (b) Manter: os dois artigos já ficam separados e, sem pista da busca, vale o primeiro do documento. | Aberta; medir no CT-98. |

Fora do escopo: perguntas por agrupamentos ("explique o capítulo I"), remissões entre artigos
("conforme o art. 7º"), comparação de versões de lei, jurisprudência e súmulas. Ficam como
evolução possível.

## Requisitos funcionais

- **RF-82**: a extração reconhece a estrutura normativa (D3, D4) e cada trecho de um artigo leva
  o caminho da estrutura no `section_path` e no prefixo do texto.
- **RF-83**: o payload de cada trecho de documento normativo inclui `legal_article` (ex.: `5`,
  `5-A`), com índice no Qdrant; trechos fora de artigo não têm o campo.
- **RF-84**: a tokenização da busca esparsa aplica a normalização da D5, igual na indexação e na
  pergunta.
- **RF-85**: o chat detecta referências a artigo, inciso e parágrafo na pergunta (já reescrita
  pelo RF-36) e monta o contexto conforme D6, D7 e D8. O evento de log
  `chat.context.structural` registra o artigo, o documento escolhido, os trechos lidos e os que
  ficaram de fora.
- **RF-86**: a instrução de sistema inclui a regra de formato da D1 e D2.

## Regras de negócio

- **RN-34**: o contexto estrutural respeita os mesmos filtros de acesso (`user_groups`) e de
  ciclo de vida (`active`) da busca híbrida; um usuário sem acesso ao documento recebe o mesmo
  fallback de hoje.
- **RN-35**: resposta sem citação válida continua indo para o fallback (RN-18), também no caminho
  estrutural.
- **RN-36**: quando o contexto estrutural não cobre o dispositivo inteiro, a resposta informa o
  intervalo omitido (D8).

## Critérios de aceite

```gherkin
Cenário: pergunta pelo número do artigo (RF-84, RF-85)
  Dado um assistente com o regulamento fictício indexado
  Quando o usuário pergunta "Explique o artigo 5"
  Então o contexto contém todos os trechos do Art. 5º, em ordem
  E a resposta lista todos os incisos do Art. 5º, cada um com citação
  E termina com um resumo explicativo

Cenário: grafias diferentes da mesma referência (RF-84)
  Quando o usuário pergunta "art. 5º", "Art 5o" ou "artigo 5"
  Então as três perguntas recuperam o Art. 5º
  E "artigo quinto" segue a busca híbrida (número por extenso fora do escopo)

Cenário: inciso específico (RF-85, D6)
  Quando o usuário pergunta "o que diz o inciso XI do art. 5º?"
  Então o contexto contém o caput do Art. 5º e o trecho do inciso XI
  E a resposta é sucinta

Cenário: artigo grande demais para o orçamento (RN-36)
  Dado STRUCTURAL_CONTEXT_TOKEN_BUDGET menor que o artigo
  Quando o usuário pergunta pelo artigo
  Então a resposta cobre os itens que couberam e informa o intervalo omitido

Cenário: artigo em dois documentos (D7)
  Dado o regulamento fictício e um segundo documento fictício, ambos com Art. 5º
  Quando o usuário pergunta "artigo 5 do regulamento"
  Então o contexto vem só do regulamento

Cenário: documento restrito (RN-34)
  Dado que o regulamento é restrito ao grupo "juridico"
  E o usuário não pertence a "juridico"
  Quando pergunta "Explique o artigo 5"
  Então recebe o fallback e nenhum trecho do regulamento é usado

Cenário: documento comum que cita artigos (D3)
  Dado um manual com duas menções a "art. 7 da CLT"
  Quando o manual é indexado
  Então o modo normativo não é ativado e os trechos ficam como hoje

Cenário: resposta sucinta (RF-86)
  Quando o usuário faz uma pergunta conceitual sobre o regulamento
  Então a resposta não repete o texto dos trechos e cabe em poucos parágrafos
```

## Impacto arquitetural

- **Domínio:** função pura de reconhecimento de referências normativas (`domain/legal_references.py`:
  título de dispositivo na linha, referência na pergunta, normalização de ordinal e romano) —
  sem dependência externa. `SearchResult` e `VectorChunk` ganham `legal_article: str | None`.
  Porta `VectorStoreGateway` ganha `fetch_article(collection, article, user_groups, limit)`.
- **Aplicação:** `ContextRetriever` ganha o caminho estrutural (D6, D7); `fit_context` recebe o
  orçamento estrutural e devolve o que ficou de fora; `ChatWithAssistantUseCase` ganha um nó no
  grafo antes de `evaluate_context`; `build_answer_instruction` inclui a regra de formato.
  `PIPELINE_VERSION` passa a `4`. A avaliação usa o mesmo caminho do chat.
- **Infraestrutura:** extração (PDF, DOCX, texto) com o modo normativo; tokenização do BM25;
  `QdrantVectorStore` grava `legal_article`, cria o índice de payload e implementa
  `fetch_article` com `scroll` filtrado.
- **API e frontend:** sem mudança de contrato. O frontend já renderiza Markdown (listas
  numeradas) com `markdown.pipe`.
- **Banco:** nenhuma migração. **Variáveis novas:** `STRUCTURAL_CONTEXT_TOKEN_BUDGET`.
- **Operação:** reindexar todos os assistentes depois do deploy (fluxo de reindexação existente).

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-91 | Reconhecimento de títulos normativos (níveis da D4), limiar de 5 artigos da D3, prefixo com `Art. N` em todo trecho do artigo | Unitário |
| CT-92 | Tokenização BM25 da D5: `5º`/`5o`/`5ª` → `5`, `artigo`/`art`, `§`/`parágrafo`; documento e pergunta geram os mesmos termos | Unitário |
| CT-93 | Detecção de referência na pergunta: artigo, `-A`, inciso em romano, parágrafo, parágrafo único; perguntas sem referência não disparam | Unitário |
| CT-94 | Contexto estrutural: artigo inteiro em ordem, filtros de acesso e `active`, escolha de documento da D7, orçamento e intervalo omitido da D8 | Unitário (dublês) |
| CT-95 | Instrução de sistema com a regra de formato; o prompt inicial do assistente vem antes | Unitário |
| CT-96 | `fetch_article` no Qdrant real: filtro de grupos, `active` e ordem por `chunk_index` | Integração (Docker) |
| CT-97 | Conjunto `normativo-ficticio`: recall@k e MRR nas perguntas por dispositivo; sem regressão em `nexus-docs` e `nexus-docs-ampliado` acima de `EVAL_REGRESSION_TOLERANCE` | Avaliação |
| CT-98 | Validação manual com a Constituição: "Explique o artigo 5" lista os 78 incisos e os parágrafos com citações e resumo; "inciso XI do art. 5º" responde sucinto | Manual (ambiente do autor) |

## Riscos

- **Falso positivo do modo normativo:** um documento com muitas linhas iniciadas por "Art." que
  não seja norma. Mitigação: limiar da D3 e só linhas que começam com `Art. <número>`.
- **Custo e latência:** o caminho estrutural envia até 16 mil tokens ao LLM. No `gpt-4o-mini`,
  cerca de US$ 0,0025 por pergunta só de entrada, mais a saída (uma lista de 78 itens tem cerca de 3
  mil tokens). A resposta longa depende do streaming; no modo sem streaming, o tempo limite de
  30 s da leitura pode ser atingido. Medir no CT-98.
- **Formatação do PDF:** PDFs com "Art. 5º" quebrado em duas linhas, ou com texto revogado
  tachado (comum no site do Planalto), podem confundir o reconhecimento. O CT-98 usa o PDF real
  do autor; ajustes de heurística entram como decisão nova.
- **Pergunta reescrita (RF-36):** o caminho estrutural usa a pergunta reescrita pelo LLM; a
  reescrita pode perder o "art. 5º" ou trazer do histórico um artigo que o usuário não pediu agora.
- **Reindexação obrigatória:** até reindexar, as bases antigas seguem sem o campo
  `legal_article` e com a tokenização anterior; o caminho estrutural não dispara nelas e o
  comportamento é o de hoje.

## Revisão do pipeline (2026-10-26)

Revisor independente (`rag-quality-reviewer`) sobre o código entregue. Corrigidos no mesmo dia,
com testes:

- **A1** — artigo com separador de milhar ("Art. 1.228." do Código Civil) virava `Art. 1`: o número
  aceita milhar e o identificador fica `1228` (título, caminho e pergunta).
- **M3** — "art. 5, vi que..." virava o inciso VI: depois da vírgula, romano em minúsculas só vale
  seguido de pontuação, fim ou "do/da"; incisos limitados a CCCXCIX (evita "DI", "MDC").
- **B2** — a auditoria (RF-45) registrava o artigo lido inteiro: passa a registrar só os trechos
  enviados ao LLM.
- **B3** — o teto de leitura do artigo era aplicado antes da ordem: teto elevado para 2.000
  trechos e evento `retrieval.article.truncated` quando atingido.

Viraram decisões pendentes: A2 (D11), M1 (D12) e M2 (D13). Confirmados sem problema: ordem do
grafo e rastreamento por nó, fallback sem LLM no caminho híbrido, filtros de grupo e `active` no
`fetch_article`, orçamento sem misturar trechos, citações, eventos do streaming, consumo e o
domínio sem dependência externa. O aviso de omissão só leva rótulos validados (romano, `§ n`,
"Parágrafo único"), sem texto livre do documento.
