# Plano Incremental

## 1. Fundação Documental

Objetivo: deixar visão, escopo, arquitetura e decisões principais compreensíveis antes do código.

Entregáveis:

- documentação de negócio
- documentação de arquitetura
- ADRs iniciais
- documentação de infraestrutura local
- estrutura base de pastas

Validação:

- revisar se o MVP está claro
- confirmar que decisões técnicas têm justificativa
- garantir que próximos passos são pequenos e testáveis

## 2. Ambiente Docker Mínimo

Objetivo: criar o `compose.yaml` com serviços base.

Entregáveis:

- `compose.yaml`
- Dockerfile do backend
- Dockerfile do frontend
- PostgreSQL com volume
- Qdrant com volume
- `.env.example`

Validação:

- `docker compose up --build`
- healthcheck da API
- Qdrant acessível
- PostgreSQL acessível

## 3. Fundação do Domínio Backend

Objetivo: modelar o núcleo sem depender de infraestrutura.

Entregáveis:

- entidades de assistente, documento, conversa e mensagem
- value objects principais
- interfaces de repositório, vector store, embeddings e LLM
- casos de uso puros iniciais

Validação:

- testes unitários sem Docker
- cobertura dos invariantes do domínio

## 4. Persistência e Assistentes

Objetivo: persistir assistentes e histórico.

Entregáveis:

- models e migrations
- repositórios PostgreSQL
- rotas de assistentes
- rotas de conversas

Validação:

- testes de integração com PostgreSQL em Docker
- criação e consulta de assistentes
- retomada de conversa

## 5. Ingestão e RAG

Objetivo: indexar documentos e recuperar contexto por assistente.

Entregáveis:

- upload de documentos
- extração de texto
- chunking
- embeddings locais
- gravação em Qdrant
- busca semântica isolada por collection

Validação:

- dois assistentes com documentos distintos
- busca sem mistura entre collections
- metadados mínimos por chunk

## 6. Fluxo Conversacional

Objetivo: conectar recuperação, avaliação e resposta.

Entregáveis:

- grafo LangGraph
- adapter de LLM configurável
- fallback para contexto insuficiente
- persistência de pergunta e resposta

Validação:

- testes com LLM fake
- resposta baseada em contexto recuperado
- fallback quando não há evidência

## 7. Frontend Angular

Objetivo: entregar a experiência mínima de uso.

Entregáveis:

- layout base
- seleção e criação de assistentes
- upload de documentos
- chat com Markdown
- store NgRx para estado principal

Validação:

- testes de componentes/store
- fluxo manual no Docker

## 8. Integração E2E do MVP

Objetivo: provar o ciclo completo.

Entregáveis:

- integração frontend-backend
- documentação de execução
- ajustes de UX e erros comuns

Validação:

- criar assistente
- enviar documento
- perguntar sobre o documento
- receber resposta baseada no conteúdo
- reiniciar ambiente e retomar histórico

---

# Evolução RAG Enterprise

As etapas 1 a 8 construíram o MVP. As etapas 9 a 14 levam o RAG ao nível corporativo. Cada etapa
tem uma especificação SDD em [`docs/especificacao/specs/`](especificacao/specs/README.md), que
precisa estar aprovada antes do início da implementação. Em 2026-10-08 o código das etapas 9 a 14
está entregue e coberto por testes unitários, mas nenhuma etapa foi validada no ambiente Docker. O
que falta para concluir está no [plano de conclusão](plano-de-conclusao.md).

Decisões fixadas para todas as etapas: embeddings locais (ADR 0004) e Keycloak como provedor de
identidade (ADR 0008).

## 9. Avaliação e Linha de Base

Objetivo: medir a qualidade atual e poder comparar toda mudança futura.

Especificação: [SPEC-001](especificacao/specs/SPEC-001-avaliacao-e-linha-de-base.md).
Estimativa: 1 a 2 semanas.

Situação (2026-10-24): validada na campanha `validacao-final-rc8` (testes de integração e avaliação
no Docker). Conjunto ampliado para 82 itens (`nexus-docs-ampliado`), validado pelo curador; linha de
base oficial registrada (recall@5 0,984, fidelidade média 0,994). Ver o [RESUMO da validação](qa/relatorios/2026-10-24-rc8/RESUMO-validacao-final.md).

Entregáveis:

- conjunto de referência do assistente piloto
- caso de uso e comando de avaliação
- relatório de linha de base do pipeline atual
- logs estruturados com identificador de requisição

Validação:

- relatório com recall@5, MRR, fidelidade e fallback correto gerado por um comando
- regressão simulada faz o comando falhar
- arquivo de depuração removido

## 10. Recuperação Semântica

Objetivo: substituir o embedding por hash pelo modelo local da ADR 0004 e o corte fixo por
chunking estrutural.

Especificação: [SPEC-002](especificacao/specs/SPEC-002-recuperacao-semantica.md).
Estimativa: 3 a 4 semanas.

Situação (2026-10-24): validada no Docker na campanha `rc8`: modelo real, migrações e troca de alias
(CT-10 a CT-12); recall@5 0,984. Ver o [RESUMO da validação](qa/relatorios/2026-10-24-rc8/RESUMO-validacao-final.md).

Entregáveis:

- adaptador de embeddings com sentence-transformers
- chunker estrutural medido em tokens
- metadados de seção, página e modelo por chunk
- collections versionadas com alias e reindexação
- migrações versionadas de banco

Validação:

- recall@5 de pelo menos 0,80 no assistente piloto
- ingestão funciona sem acesso à internet
- reindexação sem interromper consultas

## 11. Busca Híbrida, Reranking e Citações

Objetivo: acertar termos exatos, ordenar melhor os trechos e mostrar a origem das respostas.

Especificação: [SPEC-003](especificacao/specs/SPEC-003-busca-hibrida-reranking-citacoes.md).
Estimativa: 3 a 4 semanas.

Situação (2026-10-24): validada na campanha `rc8`: busca híbrida, rerank e citações (CT-18 a CT-20);
fidelidade média 0,994, fallback fora do escopo 0,90 e 100% das respostas geradas com citação; nota
mínima calibrada em 0,10. A exibição das fontes no chat (RF-38) fecha com a V5. Ver o [RESUMO da validação](qa/relatorios/2026-10-24-rc8/RESUMO-validacao-final.md).

Entregáveis:

- vetor esparso BM25 e busca híbrida com RRF
- reranker local
- nota mínima de relevância
- reescrita da pergunta com o histórico
- citações persistidas e exibidas no chat
- orçamento de tokens

Validação:

- toda resposta gerada exibe fontes
- perguntas fora do escopo resultam em fallback em pelo menos 90% dos casos
- fidelidade de pelo menos 0,90

## 12. Autenticação e Controle de Acesso

Objetivo: autenticar pelo Keycloak e restringir assistentes e documentos por grupo.

Especificação: [SPEC-004](especificacao/specs/SPEC-004-autenticacao-e-controle-de-acesso.md).
Estimativa: 3 a 4 semanas.

Situação (2026-10-24): validada na campanha `rc8`: Keycloak real (CT-52), permissões (CT-26 a CT-31) e
varredura de vazamento com zero ocorrências (CT-56). Tela de conversas arquivadas, seleção de grupos e
origens configuráveis entregues (PC-D1, PC-D5, PC-D6). Os cenários E1, E5 e E6 fecham com a V5. Ver o [RESUMO da validação](qa/relatorios/2026-10-24-rc8/RESUMO-validacao-final.md).

Entregáveis:

- serviço Keycloak com realm de desenvolvimento
- validação de token e política de acesso no domínio
- permissões por assistente e por documento
- conversas privadas
- trilha de auditoria
- login, guards e telas administrativas no frontend

Validação:

- nenhuma rota responde sem token válido, exceto `/health`
- usuário de um grupo não recupera trecho de documento restrito a outro
- rotas da chave do LLM restritas ao administrador

## 13. Ingestão e Ciclo de Vida de Documentos

Objetivo: processar em segundo plano e manter a base atual.

Especificação: [SPEC-005](especificacao/specs/SPEC-005-ingestao-e-ciclo-de-vida.md).
Estimativa: 2 a 3 semanas.

Situação (2026-10-24): validada na campanha `rc8`: ingestão assíncrona, OCR, reindexação no worker e
conferência PostgreSQL × Qdrant (CT-37 a CT-40, CT-53, CT-57); upload de 25 MB em até 1,36 s (RNF-17).
A indexação de 10 MB ficou acima de 60 s e foi aceita como limitação (PC-D11); tabelas em PDF seguem
adiadas (D11). Ver o [RESUMO da validação](qa/relatorios/2026-10-24-rc8/RESUMO-validacao-final.md).

Entregáveis:

- fila em PostgreSQL e serviço worker
- estados do documento e novas tentativas
- armazenamento dos arquivos originais
- exclusão, substituição, deduplicação e reprocessamento
- OCR local

Validação:

- upload responde em até 2 segundos
- excluir um documento remove seus vetores
- reinício do worker não duplica chunks

## 14. Operação e Governança

Objetivo: tornar falhas, custos e abusos visíveis e controláveis.

Especificação: [SPEC-006](especificacao/specs/SPEC-006-operacao-e-governanca.md).
Estimativa: 1 a 2 semanas.

Situação (2026-10-24): validada na campanha `rc8`: rastreamento e métricas, streaming, logs sem dados
sensíveis, backup e restauração e portão de regressão (CT-44 a CT-48); primeiro texto do chat com p95
de 7,4 s (RNF-01). Os cenários E7, E8 e E11 fecham com a V5. Ver o [RESUMO da validação](qa/relatorios/2026-10-24-rc8/RESUMO-validacao-final.md).

Entregáveis:

- rastreamento e métricas
- consumo e custo estimado por conversa
- resposta em streaming
- limite de uso
- proteção contra injeção de prompt
- feedback de resposta
- avaliação na integração contínua
- backup e restauração

Validação:

- cada resposta rastreável por um identificador
- regressão de qualidade bloqueia a integração contínua
- restauração de backup em ambiente limpo

## Estimativa Total e Pontos de Decisão

De 13 a 19 semanas para uma pessoa dedicada, sem incluir homologação com usuários nem implantação
em produção. As etapas 9 e 10 entregam a maior parte do ganho de qualidade em 4 a 6 semanas. Há um
ponto de reavaliação de prioridades ao fim da etapa 11.

## Conclusão

O trabalho restante (lacunas de código, preparação e campanha de validação, atualização da
documentação) está ordenado no [plano de conclusão](plano-de-conclusao.md), com meta de encerramento
em 2026-11-19.
