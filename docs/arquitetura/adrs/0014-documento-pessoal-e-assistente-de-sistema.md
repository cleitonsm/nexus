# ADR 0014: Documento pessoal e assistente de sistema

## Status

Aceita em 2026-10-30, com a aprovação da [SPEC-018](../../especificacao/specs/SPEC-018-resumidor-de-documentos.md).
Complementa a [ADR 0003](0003-qdrant-por-assistente.md), a [ADR 0008](0008-keycloak-e-modelo-de-permissoes.md)
e a [ADR 0009](0009-ingestao-assincrona.md). Mantém a [ADR 0004](0004-embedding-local-sem-llm.md) sem mudança.

## Contexto

Até a SPEC-017, todo documento do Nexus pertence à **base de um assistente**. Só o administrador ou o
curador do assistente envia arquivos (ADR 0008), e o usuário comum consulta a base filtrada pelos
grupos dele. Todo assistente é criado por um administrador.

A SPEC-018 pede um "Resumidor de documentos" que:

- existe para todo usuário sem que ninguém o crie;
- recebe arquivos **do próprio usuário**, visíveis só a ele;
- gera um resumo hierárquico gravado e responde perguntas pontuais pelo RAG.

Nenhuma dessas três coisas cabe no modelo atual: não há assistente sem dono administrativo, não há
documento com dono individual, e o isolamento na busca é só por grupo.

## Decisão

1. **Assistente de sistema.** A coluna `assistants.system_kind` (índice único parcial) marca
   assistentes que a migração cria e que existem para todo usuário com papel no Nexus, sem grupo.
   Hoje só existe `document_summarizer`, com id fixo (`SUMMARIZER_ASSISTANT_ID`). Um assistente de
   sistema não pode ser excluído nem ter perfil, recuperação ou base alterados (409
   `system_assistant_readonly`). O administrador troca só a credencial e o modelo (ADR 0013). O
   prompt dele fica versionado no código.
2. **Documento pessoal.** É uma linha em `documents` com `owner_user_id` e `conversation_id`,
   sempre do assistente de sistema. Quem envia é qualquer usuário com papel, só na própria conversa
   e no máximo um documento por conversa. A leitura segue a regra das conversas (RN-24): só o dono,
   **nem o administrador**. Conversa alheia responde 404.
3. **Isolamento numa única collection.** Os documentos pessoais ficam todos em
   `assistant_{SUMMARIZER_ASSISTANT_ID}`, coerente com a ADR 0003 (uma collection por assistente).
   Cada ponto grava `owner_user_id`, `conversation_id` e `allowed_groups` vazio, e os dois primeiros
   têm índice de payload. Toda busca nessa collection aplica os filtros de sempre (`user_groups` e
   `active`) **mais** dono e conversa. Sem o escopo pessoal, a busca é recusada antes de chegar ao
   Qdrant (**falha fechada**): ela nunca roda sem filtro.
4. **Fluxo de dados para o LLM.** Os embeddings, o BM25, o reranking e o OCR continuam locais
   (ADR 0004). No resumo, o **texto do documento vai ao LLM** configurado para o resumidor, em lotes
   de até 8.000 tokens, como os trechos recuperados já vão numa pergunta. O conteúdo vai delimitado
   como dado e passa pela checagem de injeção de prompt. A explicação mostrada ao usuário antes do
   envio diz isso.
5. **Resumo gravado.** O worker produz os mini-resumos por lote de seções e o consolidado, e grava
   os dois em `document_summaries` e `document_summary_sections`, com a versão do prompt. A entrega
   do resumo geral lê o banco, sem LLM. O job `resumo` entra na mesma fila `ingestion_jobs` (ADR
   0009), depois da indexação, com as mesmas tentativas e o mesmo limite de tempo.
6. **Retenção e lápide.** O documento pessoal expira 30 dias depois do envio, ou na exclusão da
   conversa, o que vier primeiro. O worker apaga vetores, original e mini-resumos e mantém a linha
   em `documents` como **lápide** (status `expirado`, sem conteúdo). A lápide sustenta a cota diária
   e a auditoria. A mensagem com o resumo já entregue continua na conversa, porque faz parte do
   histórico do usuário.
7. **Uso e custo.** Chamadas do resumo gravam `usage_records.operation = 'document_summary'`. Elas
   entram no custo por usuário, mas não nos limites de perguntas. O controle é uma cota própria de
   documentos por dia.

## Alternativas consideradas

| Alternativa | Por que não |
|-------------|-------------|
| Collection por conversa ou por usuário | Milhares de collections pequenas, criação e exclusão no caminho do usuário e cada uma com seus índices. O filtro por payload com índice resolve com uma collection só, como a ADR 0003 já faz por grupo |
| Pôr o documento na base de um assistente comum | Outros usuários do grupo passariam a vê-lo. Isso contraria o pedido e a RN-24 |
| Trocar o modelo de embeddings por um de contexto maior, para chunks de 500 a 1.000 tokens | Exigiria reindexar todos os assistentes e refazer a linha de base (recall@5 0,984). O resumo não usa os chunks do RAG |
| Resumir na hora do pedido | Latência de minutos e custo repetido a cada pedido. O requisito pede menos de 1 s |
| Tabela própria de documentos pessoais | Duplicaria a ingestão, o status, o OCR e a fila. Duas colunas e um check em `documents` reaproveitam tudo |

## Consequências

- A matriz de permissões da ADR 0008 ganha uma linha: "enviar documento pessoal: todo usuário com
  papel, só na própria conversa". O papel do administrador **não** inclui ler documento pessoal.
- A regra "toda busca no Qdrant filtra `user_groups` e `active`" continua valendo. Na collection do
  resumidor, dono e conversa também passam a ser obrigatórios.
- O acesso rápido (SPEC-016) passa a ter um cartão fixo fora das vagas e um novo padrão de recuo.
- Novos assistentes de sistema (outro `system_kind`) reaproveitam a decisão 1 com uma SPEC própria.
- Dado pessoal fica guardado até 30 dias. Um backup diário (SPEC-006) pode retê-lo por até mais 7
  dias, e a lápide guarda o nome do arquivo. Isso fica registrado como risco de privacidade a
  revisar se a política de retenção da organização for menor.
- O custo de LLM passa a ter uma parcela por documento (de 6 a 11 chamadas), visível nos
  relatórios por `operation`.
