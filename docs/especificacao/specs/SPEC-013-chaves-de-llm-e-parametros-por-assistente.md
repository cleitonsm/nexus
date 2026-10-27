# SPEC-013 — Várias chaves de LLM, modelo por assistente e parâmetros de recuperação por assistente

**ID**: SPEC-20261027-013
**Status**: **Aprovada** em 2026-10-27 por Cleiton Medeiros (D1 a D10 escolhidas pelo autor; todas as recomendações).
**Origem**: pedido do autor (2026-10-27): cadastrar quantas chaves de API quiser, com uma padrão;
cada assistente escolhe a chave e o modelo; híbrida, reranker, candidatos, top_k, limiar e filtros
configuráveis na tela, sem editar o `.env`.
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

1. **Uma chave só.** A ADR 0005 e o RF-47 guardam uma única chave global cifrada
   (`app_settings.global_llm_api_key`). A SPEC-008 acrescentou provedor, modelo e URL
   (`app_settings.llm_connection`), mas também globais: todos os assistentes usam o mesmo
   provedor e o mesmo modelo. Trocar de provedor mantém a chave anterior (risco da SPEC-008 D4).
2. **Parâmetros de recuperação só no ambiente.** `RETRIEVAL_CANDIDATES` (30), `RERANK_TOP_N` (5) e
   `RELEVANCE_MIN_SCORE` (0,10 calibrado no CT-22) vêm do `.env`, valem para todos os
   assistentes e exigem recriar os serviços. A SPEC-012 mostrou que um assistente normativo pede
   valores diferentes dos de uma base de RH.
3. **A busca híbrida não pode ser desligada.** A parte esparsa (BM25) sempre entra na fusão RRF.
   Em bases sem termos exatos relevantes ela só acrescenta ruído, e não há como medir isso por
   assistente.

## Objetivo

- O administrador cadastra várias chaves (credenciais), cada uma com provedor, URL, modelos
  permitidos e um modelo padrão, e marca exatamente uma como padrão do sistema.
- Cada assistente usa a credencial padrão ou escolhe outra, e escolhe um dos modelos dela.
- Cada assistente tem os próprios parâmetros de recuperação, editáveis na tela do assistente
  (onde os documentos são indexados), com o valor global como padrão.
- Nenhuma regressão: sem configuração gravada, o comportamento é idêntico ao atual.

## Decisões

| # | Escolha |
|---|---------|
| D1 | **Parâmetros por assistente** (autor, 2026-10-27). Campo sem valor gravado usa o padrão global (hoje o ambiente). A tela mostra o valor efetivo e a origem (`assistente` ou `padrão`). |
| D2 | **Filtros de segurança fixos** (autor). `user_groups` e `active` continuam obrigatórios em toda busca (RN de isolamento, ADR 0003/0008) e não aparecem como opção; a tela só informa que são sempre aplicados. Filtros configuráveis por documento, tipo ou data ficam fora desta SPEC. |
| D3 | **Reranker sempre ligado** (autor). Configuráveis: busca híbrida (liga/desliga a parte BM25; desligada = só densa, sem RRF), candidatos, top_k e limiar (nota mínima do reranker). O fallback continua dependendo da nota do reranker (ADR 0007). |
| D4 | **Modelos digitados por credencial** (autor). Ao cadastrar a credencial, o administrador informa a lista de modelos permitidos e o modelo padrão dela; o assistente escolhe um da lista. Sem consulta ao `/models` do provedor. |
| D5 | **Presets `OpenAI`, `Gemini` e `Personalizado`** (autor). Mesmos da SPEC-008 D1/D7; qualquer endpoint compatível com chat completions entra por `Personalizado`. Azure OpenAI fica fora (cabeçalho `api-key` e URL por implantação). |
| D6 | **Faixas moderadas** (autor): candidatos de 5 a 100; top_k de 1 a 20 e nunca acima dos candidatos; limiar de 0,00 a 1,00 (escala já normalizada pelo `CrossEncoderRerankerGateway`). Fora da faixa → 422. |
| D7 | **Acesso** (autor): credenciais e escolha de credencial/modelo do assistente só pelo administrador (custo e destino dos dados); parâmetros de recuperação pelo administrador e pelo curador do assistente. |
| D8 | **Preço opcional por modelo** (autor): entrada e saída por 1K tokens em cada modelo da credencial; sem preço, o consumo usa `LLM_PRICE_*` e a tela avisa. |
| D9 | **Rotas da SPEC-008 removidas** (autor): `GET/PUT /admin/llm-settings`, `PUT /admin/api-key`, o status e `POST /admin/api-key/test` deixam de existir; a tela "Chaves de LLM" substitui o formulário atual. |
| D10 | **Migração para a credencial "Padrão"** (autor). A migração `0010` cria a credencial "Padrão" com o ciphertext existente (sem decifrar), o provedor/URL/modelo de `llm_connection` (ou do ambiente) e a marca como padrão. Sem chave gravada, nenhuma credencial é criada e o chat responde como hoje sem chave. |

## Regras de negócio

- RN-37: existe no máximo uma credencial padrão; havendo pelo menos uma credencial, existe exatamente uma padrão. Marcar outra como padrão desmarca a anterior na mesma transação.
- RN-38: credencial em uso (padrão do sistema ou escolhida por algum assistente) não pode ser excluída: 409 com a lista de assistentes afetados. Modelo em uso por algum assistente não pode ser removido da lista: 409.
- RN-39: a chave é gravada só cifrada (`FernetSecretCipher`), nunca volta em resposta, log, span ou auditoria; a API e a tela mostram só nome, provedor, URL, modelos e se a chave está configurada. A rotação troca o ciphertext sem mudar o id.
- RN-40: resolução do LLM por pergunta: credencial do assistente → credencial padrão → ambiente (`LLM_MODEL`, `LLM_API_URL`, sem chave = comportamento atual). Modelo: o do assistente → o padrão da credencial.
- RN-41: resolução dos parâmetros de recuperação por pergunta: valor do assistente → ambiente → padrão em código. O `top_k` da requisição (`payload.top_k`) continua sendo só um teto abaixo do `top_k` efetivo.
- RN-42: os filtros `user_groups` e `active` são aplicados em toda busca, com híbrida ligada ou desligada, e não são configuráveis.
- RN-43: os parâmetros desta SPEC são todos de consulta; alterá-los não exige reindexação. Tamanho de trecho e parâmetros do BM25 continuam de indexação e fora do escopo.

## Requisitos funcionais

- RF-87: o administrador lista, cria, altera (nome, URL em `Personalizado`, modelos, modelo padrão, chave opcional) e exclui credenciais; nome único, até 100 caracteres.
- RF-88: o administrador marca uma credencial como padrão do sistema (RN-37).
- RF-89: o administrador testa uma credencial com um dos modelos dela (substitui `POST /admin/api-key/test`).
- RF-90: o assistente guarda a credencial (opcional, vazio = padrão) e o modelo (opcional, vazio = padrão da credencial); chat, streaming, teste, consumo e avaliação usam a resolução da RN-40.
- RF-91: o assistente guarda os parâmetros de recuperação opcionais (híbrida, candidatos, top_k, limiar); a consulta mostra valor efetivo e origem de cada um; "restaurar padrão" apaga o valor gravado.
- RF-92: a tela do assistente ganha a seção "Modelo de linguagem" (credencial e modelo) e a seção "Recuperação" (D3), com o aviso fixo dos filtros de segurança (D2), o aviso de que mudar o limiar exige recalibração e o de que a troca de modelo ou parâmetro invalida a comparação com a linha de base.
- RF-93: o menu Administração ganha a tela "Chaves de LLM" (lista, padrão, criar, editar, testar, excluir).
- RF-94: toda alteração gera auditoria com valores anteriores e novos, sem a chave: `llm_credential.created`, `.updated`, `.deleted`, `.default_changed`, `.key_rotated`; `assistant.llm_changed`; `assistant.retrieval_settings_changed`. Negativas de acesso são auditadas.
- RF-95: o relatório de avaliação e o `calibrate_relevance` registram, por assistente, credencial (nome), modelo e parâmetros efetivos; `calibrate_relevance` aceita `--assistant`.

## Critérios de aceite

```gherkin
Cenário: duas credenciais e assistentes em provedores diferentes (RF-87, RF-90)
  Dado a credencial "OpenAI" padrão e a credencial "Gemini" com o modelo "gemini-3.8-flash"
  E o assistente RH sem credencial e o assistente Jurídico com "Gemini"
  Quando cada assistente recebe uma pergunta
  Então o RH chama a OpenAI com o modelo padrão dela e o Jurídico chama o Gemini com o modelo escolhido

Cenário: trocar a padrão (RF-88, RN-37)
  Quando o administrador marca "Gemini" como padrão
  Então "OpenAI" deixa de ser padrão e o RH passa a usar "Gemini" na próxima pergunta

Cenário: excluir credencial em uso (RN-38)
  Quando o administrador exclui "Gemini" escolhida pelo Jurídico
  Então a resposta é 409 com o assistente Jurídico na lista e nada é excluído

Cenário: a chave nunca volta (RN-39)
  Quando qualquer rota de credencial responde
  Então o corpo tem "key_configured" e nunca a chave nem parte dela

Cenário: limiar por assistente (RF-91, RN-41)
  Dado o Jurídico com limiar 0,30 e o RH sem limiar gravado e o ambiente com 0,10
  Então o Jurídico usa 0,30 com origem "assistente" e o RH usa 0,10 com origem "padrão"

Cenário: híbrida desligada (D3, RN-42)
  Dado o assistente com busca híbrida desligada
  Quando o usuário pergunta
  Então a busca usa só o vetor denso, filtra user_groups e active, e o reranker continua decidindo o fallback

Cenário: faixa inválida (D6)
  Quando o top_k é maior que os candidatos ou o limiar é maior que 1
  Então a resposta é 422 e os valores anteriores são mantidos

Cenário: migração (D10)
  Dado a chave global e o llm_connection gravados antes da 0010
  Quando a migração roda
  Então existe uma credencial "Padrão" marcada como padrão com o mesmo ciphertext e o chat responde igual

Cenário: sem configuração (Objetivo)
  Dado nenhum assistente com parâmetros gravados
  Então a avaliação dos três conjuntos não regride em relação à linha de base
```

## Impacto arquitetural

- **ADR nova 0012** "Várias credenciais de LLM e configuração por assistente", substituindo em parte a 0005 (continua: chave cifrada, nunca devolvida; muda: várias chaves, uma padrão) e complementando a 0007 (híbrida desligável por assistente; reranker e nota mínima mantidos).
- **Domínio**: `LLMCredential` (id, nome, provedor, URL, modelos, modelo padrão, padrão do sistema, chave configurada), validação de URL e modelo reaproveitada de `llm_settings.py`; value object `RetrievalProfile` (campos opcionais e faixas D6); porta `LLMCredentialRepository`; `Assistant` ganha `llm_credential_id`, `llm_model` e `retrieval_profile`.
- **Aplicação**: casos de uso das credenciais (listar, criar, alterar, excluir, marcar padrão, testar), `UpdateAssistantLLMUseCase`, `UpdateAssistantRetrievalSettingsUseCase`; `resolve_llm_for_assistant` (RN-40) e `resolve_retrieval_settings` (RN-41) substituem `resolve_llm_connection` e o `retrieval_settings()` único. `chat_with_assistant` recebe as configurações resolvidas por pergunta.
- **Infraestrutura**: migração `0010` com a tabela `llm_credentials` (índice único parcial `WHERE is_default`), colunas novas em `assistants` (FK `ON DELETE RESTRICT`) e a cópia dos dados atuais (D10); `QdrantVectorStoreGateway.search` aceita híbrida desligada (só prefetch denso, sem `FusionQuery`); `HttpChatCompletionsLLM` criado por credencial resolvida.
- **API**: `/admin/llm-credentials` (`GET`, `POST`), `/{id}` (`PUT`, `DELETE`), `/{id}/default` e `/{id}/test` (`POST`); `GET /llm-credentials/options` (nome, provedor e modelos, sem chave) para o formulário do assistente; `GET/PUT /assistants/{id}/llm` e `/assistants/{id}/retrieval-settings`. Rotas da SPEC-008 conforme D9.
- **Frontend**: página `/admin/llm-credentials` no `administrationMenu`; seções novas no formulário do assistente; ações, effects, reducer e seletores NgRx; HTTP só em `nexus-api.service.ts`.
- **Variáveis de ambiente**: nenhuma nova; `RETRIEVAL_CANDIDATES`, `RERANK_TOP_N`, `RELEVANCE_MIN_SCORE`, `LLM_MODEL` e `LLM_API_URL` passam a ser só o padrão global.

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-99 | `LLMCredential`: nome, URL (regras da SPEC-008 D3), modelos sem duplicata, modelo padrão dentro da lista, preços não negativos (D8) | Unitário |
| CT-100 | `RetrievalProfile`: faixas D6, top_k ≤ candidatos, campos vazios | Unitário |
| CT-101 | RN-37: marcar padrão desmarca a anterior; primeira credencial vira padrão | Unitário |
| CT-102 | RN-38: excluir credencial ou remover modelo em uso → erro com assistentes afetados | Unitário |
| CT-103 | RN-40/41: resolução assistente → padrão → ambiente, com origem | Unitário |
| CT-104 | RN-39: respostas, logs e auditoria sem a chave; rotação mantém o id | Unitário |
| CT-105 | Permissões D7 e auditoria RF-94, inclusive negativas | Unitário |
| CT-106 | Chat e streaming usam a credencial, o modelo e os parâmetros do assistente; fallback pela nota do reranker com híbrida desligada | Unitário |
| CT-107 | Migração `0010`: dados atuais viram a credencial padrão; `downgrade` volta ao `app_settings` | Integração (Docker) |
| CT-108 | Busca só densa no Qdrant real com filtro de grupos e `active` | Integração (Docker) |
| CT-109 | Rotas novas (200, 403, 409, 422) | Integração (Docker) |
| CT-110 | Reducers, seletores e formulários (credenciais, LLM e recuperação do assistente) | Vitest |
| CT-111 | Avaliação dos três conjuntos sem configuração gravada: sem regressão | Avaliação |
| CT-112 | Duas credenciais reais (OpenAI e Gemini) em dois assistentes | Manual |

## Riscos

- Limiar por assistente sem calibração: cada assistente pode ficar com um valor sem medida. Mitigação: aviso na tela e `calibrate_relevance --assistant` (RF-95).
- Trocar a credencial padrão muda o destino dos dados de todos os assistentes sem credencial própria. Mitigação: a tela lista os assistentes afetados antes de confirmar; auditoria.
- Mais combinações para avaliar (modelo × parâmetros × assistente). O relatório registra a configuração efetiva para a comparação ficar honesta.
- Custo estimado incorreto para modelos cadastrados sem preço (D8). Mitigação: aviso na tela de chaves e no consumo.
- A configuração é lida a cada pergunta; o custo é uma consulta por pergunta ao PostgreSQL. Se o RNF-01 piorar, cachear por assistente com invalidação na alteração.
