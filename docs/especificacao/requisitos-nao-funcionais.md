# Requisitos Não Funcionais — Nexus

Notação: `RNF-XX` — Requisito Não Funcional.
Categorias conforme ISO/IEC 25010 e material do curso.

---

## Desempenho

| ID     | Descrição |
|--------|-----------|
| RNF-01 | O sistema deve retornar os primeiros tokens da resposta do chat em até 30 segundos para 95% das requisições em condições normais de operação com LLM externo. |
| RNF-02 | A indexação de um documento de até 10 MB deve ser concluída em até 60 segundos. |
| RNF-03 | A busca vetorial deve retornar os `top-k` chunks em menos de 2 segundos para bases com até 100.000 vetores. |

## Segurança

| ID     | Descrição |
|--------|-----------|
| RNF-04 | A chave de API do provedor LLM deve ser armazenada criptografada no banco de dados usando cifra simétrica (Fernet). |
| RNF-05 | A chave de criptografia não deve ser armazenada no banco de dados; deve ser fornecida via variável de ambiente. |
| RNF-06 | O sistema não deve expor a chave de API do LLM em nenhuma resposta de API pública. |

## Isolamento de Dados

| ID     | Descrição |
|--------|-----------|
| RNF-07 | Cada assistente deve possuir uma collection independente no Qdrant; uma consulta de um assistente não deve acessar vetores de outro. |
| RNF-08 | A exclusão de um assistente deve remover a collection associada no Qdrant, garantindo que nenhum dado residual permaneça. |

## Portabilidade e Implantação

| ID     | Descrição |
|--------|-----------|
| RNF-09 | O ambiente completo (backend, frontend, banco de dados, vetor store) deve subir localmente com um único comando (`docker compose up`) sem instalar dependências na máquina host. |
| RNF-10 | O sistema deve ser compatível com provedores LLM que implementam a interface OpenAI Chat Completions (ex.: OpenAI, Gemini via proxy, LM Studio). |

## Manutenibilidade

| ID     | Descrição |
|--------|-----------|
| RNF-11 | O backend deve seguir Clean Architecture, separando domínio, aplicação, infraestrutura e API, de modo que a troca do provedor LLM, banco de dados ou vetor store exija alterações apenas na camada de infraestrutura. |
| RNF-12 | O frontend deve seguir o padrão NgRx com estado centralizado, garantindo que toda mutação de estado seja rastreável por ação/reducer. |

## Usabilidade

| ID     | Descrição |
|--------|-----------|
| RNF-13 | O sistema deve fornecer feedback visual (indicador de carregamento) para todas as operações assíncronas com duração superior a 500 ms. |
| RNF-14 | O sistema deve exibir mensagens de erro compreensíveis ao usuário para falhas de comunicação com o LLM ou com a API. |
| RNF-15 | A interface deve ser responsiva, funcionando adequadamente em telas com largura mínima de 360 px. |

---

# Evolução — RAG Enterprise

**Situação em 2026-10-07:** a Fase 1 atende parcialmente o RNF-25 e o RNF-29 (logs estruturados sem
segredos e identificador de requisição no backend) e fornece o instrumento de medida dos RNF-19 a
RNF-21. Os demais requisitos ainda não foram implementados. As metas numéricas são valores iniciais,
a calibrar após a linha de base medida na Fase 1 (ver
[`specs/SPEC-001-avaliacao-e-linha-de-base.md`](specs/SPEC-001-avaliacao-e-linha-de-base.md)).

Requisitos do MVP revisados por esta evolução:

- **RNF-02** passa a medir o tempo de processamento em segundo plano; o tempo de resposta do
  upload é tratado pelo RNF-17.

## Desempenho

| ID     | Descrição |
|--------|-----------|
| RNF-16 | A recuperação (busca híbrida e reranking) deve ser concluída em até 3 segundos para 95% das perguntas, em CPU, para bases com até 100.000 chunks. |
| RNF-17 | O upload de um documento de até 25 MB deve responder em até 2 segundos, devolvendo o identificador e o estado inicial do documento. |
| RNF-18 | A reindexação de um assistente não deve interromper nem degradar as consultas à base vigente. |

## Qualidade da Resposta

| ID     | Descrição |
|--------|-----------|
| RNF-19 | O recall@5 da recuperação deve ser de no mínimo 0,80 no conjunto de referência de cada assistente piloto. |
| RNF-20 | A fidelidade das respostas ao contexto recuperado deve ser de no mínimo 0,90 no conjunto de referência. |
| RNF-21 | Pelo menos 90% das perguntas fora do escopo da base devem resultar em fallback explícito. |

## Segurança e Privacidade

| ID     | Descrição |
|--------|-----------|
| RNF-22 | Todo token de acesso deve ser validado no backend quanto a assinatura (JWKS do Keycloak), emissor, audiência e expiração. |
| RNF-23 | As restrições de acesso devem ser aplicadas no servidor, dentro da consulta ao vector store; o frontend nunca é a única barreira. |
| RNF-24 | A trilha de auditoria deve ser somente de inclusão (append-only), com retenção configurável e padrão de 12 meses. |
| RNF-25 | Logs, rastreamentos e métricas não devem conter segredos, tokens de acesso nem o conteúdo integral de documentos. |
| RNF-26 | Embeddings densos, vetores esparsos, reranking e OCR devem ser executados localmente; nessas etapas nenhum conteúdo de documento pode sair do ambiente (ADR 0004). |

## Confiabilidade

| ID     | Descrição |
|--------|-----------|
| RNF-27 | O processamento de ingestão deve ser idempotente e retomável: a falha ou reinício do worker não pode perder nem duplicar documentos. |
| RNF-28 | O ponto de recuperação (RPO) dos dados relacionais e vetoriais deve ser de no máximo 24 horas. |

## Observabilidade

| ID     | Descrição |
|--------|-----------|
| RNF-29 | Toda requisição de chat deve ser rastreável de ponta a ponta por um único identificador, da interface até a chamada ao LLM. |

## Manutenibilidade

| ID     | Descrição |
|--------|-----------|
| RNF-30 | Todo componente novo deve ser introduzido atrás de uma porta do domínio, com cobertura de testes unitários de no mínimo 80% nas camadas de domínio e aplicação. |
| RNF-31 | Toda alteração de esquema do banco deve ser feita por migração versionada e reversível. |

## Portabilidade e Implantação

| ID     | Descrição |
|--------|-----------|
| RNF-32 | O ambiente completo, incluindo Keycloak e worker de ingestão, deve continuar subindo com um único comando, com os modelos locais mantidos em volume de cache. |

## Usabilidade

| ID     | Descrição |
|--------|-----------|
| RNF-33 | As fontes de uma resposta devem estar acessíveis em um clique, e o estado de ingestão deve ser atualizado na interface sem recarregar a página. |
