# ADR 0013: Várias credenciais de LLM e configuração por assistente

## Status

Aceita em 2026-10-27, com a aprovação da SPEC-013. Implementada; validação no ambiente Docker
pendente (P8 do plano). Substitui em parte a [ADR 0005](0005-api-key-global-criptografada.md) e
complementa a [ADR 0007](0007-busca-hibrida-e-reranking.md).

## Contexto

A ADR 0005 guarda uma única chave global cifrada, e a SPEC-008 acrescentou provedor, modelo e URL,
também globais. Todos os assistentes falam com o mesmo provedor e o mesmo modelo, e trocar de
provedor mantinha a chave anterior, que passava a ser enviada a outro destino. Os parâmetros de
recuperação da ADR 0007 (candidatos, top_k, nota mínima) vêm só do ambiente e valem para todos
os assistentes, embora uma base normativa (SPEC-012) peça valores diferentes de uma base de RH.

## Decisão

1. **Credenciais.** Tabela `llm_credentials` (migração `0010`): nome, provedor (`openai`,
   `gemini`, `custom`), URL, modelos permitidos com preço opcional por 1K tokens, modelo padrão e
   a chave, só cifrada (Fernet, `NEXUS_SECRETS_KEY`, como na ADR 0005). Exatamente uma é a padrão
   quando há alguma; o banco garante no máximo uma (índice único parcial).
2. **Chave nunca volta.** Respostas, logs, spans, auditoria e `repr` levam só `key_configured`;
   a chave é decifrada em memória, a cada pergunta, só para a chamada. O 422 de validação não
   devolve o corpo recebido. Trocar provedor ou URL exige chave nova (D12).
3. **Assistente.** Guarda credencial, modelo e perfil de recuperação, todos opcionais. Resolução
   por pergunta: credencial do assistente → credencial padrão → ambiente; modelo do assistente →
   padrão da credencial, com recuo ao padrão quando quem segue a padrão guardou um modelo que ela
   não tem (D11). Credencial ou modelo em uso não podem sair (FK `RESTRICT` e regra de domínio).
4. **Recuperação por assistente.** Busca híbrida (liga ou desliga só a parte BM25), candidatos,
   top_k e nota mínima, nas faixas da D6; campo vazio segue o ambiente. O reranker continua sempre
   ligado e decidindo o fallback; os filtros de `user_groups` e `active` não são configuráveis.
   Busca só densa = vetor esparso vazio; o adaptador do Qdrant faz só a pré-busca densa, com os
   mesmos filtros.
5. **Acesso.** Credenciais e escolha do LLM do assistente só pelo administrador; parâmetros de
   recuperação também pelo curador do assistente; o curador consulta o LLM efetivo (T8).
6. **Fim da configuração global.** Saem as rotas, os casos de uso e o repositório da SPEC-008
   (`/admin/api-key*`, `/admin/llm-settings`); a migração `0011` apaga a chave global e o
   `llm_connection` depois de a `0010` copiá-los para a credencial "Padrão".

## Consequências

- Cada assistente pode usar um provedor e um modelo próprios, e o custo estimado usa o preço do
  modelo quando informado (sem ele, `LLM_PRICE_*`).
- O ambiente (`LLM_MODEL`, `LLM_API_URL`, `RETRIEVAL_CANDIDATES`, `RERANK_TOP_N`,
  `RELEVANCE_MIN_SCORE`) passa a ser só o padrão global.
- A avaliação e a calibração usam a mesma resolução do chat e registram credencial, modelo, juiz,
  origem de cada parâmetro e se a configuração difere da linha de base.
- Cada pergunta faz algumas consultas a mais ao PostgreSQL (credencial e chave). Se o RNF-01
  piorar, cachear por assistente com invalidação na alteração.
- Mais combinações a avaliar (modelo × parâmetros × assistente): a nota mínima de cada assistente
  precisa de calibração própria (`calibrate_relevance --assistant`).
