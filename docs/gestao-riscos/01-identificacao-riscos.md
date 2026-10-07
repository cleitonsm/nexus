# Etapa 1 — Identificação de Riscos

## Prompt utilizado

```
Persona: Você atua como um especialista em gerenciamento de riscos em projetos de
software, com experiência na identificação de riscos técnicos, organizacionais e de
processo, especialmente em contextos de alta incerteza.

Tarefa: Identificar possíveis riscos associados ao projeto, com base nas informações
fornecidas, considerando fatores que podem impactar o andamento, a qualidade ou os
resultados do projeto.

Contexto:
- Projeto: Nexus, uma plataforma RAG (Retrieval-Augmented Generation) que centraliza
  conhecimento organizacional em assistentes conversacionais isolados por base de
  conhecimento (uma collection Qdrant por assistente).
- Stack: FastAPI + Clean Architecture (backend), Angular + NgRx (frontend), PostgreSQL,
  Qdrant, embeddings locais (sentence-transformers), LangGraph para o fluxo
  conversacional, provedor de LLM externo configurável via variável de ambiente.
- Projeto acadêmico (pós-graduação), desenvolvido em ciclos incrementais por um único
  desenvolvedor, com prazo fixo de entrega.
- Decisões já registradas em ADR: isolamento por collection (ADR 0003), embeddings
  locais sem custo por chamada (ADR 0004), API key global criptografada sem camada de
  autenticação administrativa (ADR 0005).
- Ambiente executado localmente via Docker Compose.

A análise deve se limitar às informações fornecidas e suas implicações diretas.

Saída: lista de riscos, cada um com descrição breve e contexto de ocorrência. Não
assumir informações não fornecidas explicitamente; indicar quando houver incerteza.
```

## Saída gerada pela IA (revisada pelo autor)

| # | Risco | Descrição | Contexto de ocorrência |
|---|---|---|---|
| R1 | Contaminação de contexto entre assistentes | Uma falha na estratégia de isolamento por collection (bug de roteamento, exclusão parcial ou reuso indevido de `assistant_id`) pode fazer um assistente recuperar trechos de outra base de conhecimento. | Ao criar/excluir assistentes rapidamente durante testes, ou se o `assistant_id` não for propagado corretamente do frontend até a busca vetorial. |
| R2 | Respostas irrelevantes ou alucinadas por recuperação mal calibrada | Chunking mal dimensionado, poucos documentos indexados ou threshold de relevância mal ajustado no LangGraph podem levar a respostas genéricas ou ao fallback ser acionado (ou não) de forma incorreta. | Documentos muito longos, mal formatados (PDFs escaneados, DOCX com tabelas complexas) ou avaliação de relevância pouco rigorosa. |
| R3 | Vazamento da API key do provedor de LLM | Apesar da criptografia em repouso (ADR 0005), a chave é descriptografada em memória no momento da chamada; erros de log, exceptions não tratadas ou dependências desatualizadas podem expor o segredo. | Logs de erro muito verbosos, ferramentas de observabilidade mal configuradas, ou biblioteca de terceiros com vulnerabilidade. |
| R4 | Indisponibilidade ou mudança do provedor de LLM externo | O adapter de LLM depende de um serviço externo; instabilidade, mudança de contrato de API ou limite de taxa (rate limit) podem interromper o fluxo conversacional. | Picos de uso durante demonstração/avaliação acadêmica, ou mudança de versão da API do provedor. |
| R5 | Acesso indevido ao endpoint administrativo | O endpoint de configuração da API key não possui autenticação própria nesta fase do MVP (conforme ADR 0005), dependendo apenas do isolamento de rede. | Exposição acidental do ambiente fora da rede controlada (ex.: deploy de demonstração em rede pública sem proxy/firewall). |
| R6 | Atraso de cronograma por dependência de um único desenvolvedor | O projeto é construído por uma pessoa, em ciclos incrementais, com prazo acadêmico fixo; qualquer imprevisto (saúde, carga de trabalho, complexidade subestimada) impacta diretamente o cronograma, sem redundância de equipe. | Concentração de etapas críticas (ex.: fluxo conversacional, integração E2E) próximas ao prazo final de entrega. |
| R7 | Instabilidade do ambiente Docker local | Conflitos de porta (4200, 8000, 5432, 6333), falhas de comunicação entre containers ou lentidão dos embeddings locais por limitação de CPU/memória podem impedir a validação do fluxo completo. | Máquina de desenvolvimento com recursos limitados, ou execução simultânea de outros serviços nas mesmas portas. |
| R8 | Divergência entre documentação e implementação | Como o projeto documenta decisões via ADR e plano incremental antes/durante a construção, mudanças de escopo ao longo dos ciclos podem deixar a documentação desatualizada em relação ao código. | Ajustes de última hora em funcionalidades já documentadas, sem atualização correspondente dos ADRs ou do plano incremental. |

*Observação: os riscos R1, R2, R7 e R8 já eram parcialmente antecipados nas seções "Consequências" dos ADRs e no [`troubleshooting.md`](../infraestrutura/troubleshooting.md); os riscos R3, R5 e R6 foram trazidos de forma mais explícita pela análise da IA, ampliando a cobertura em relação ao que já estava documentado.*

---

# Ciclo 2 — Evolução RAG Enterprise

Os riscos R1 a R8 acima referem-se ao MVP. Este ciclo identifica os riscos da evolução planejada
em [`docs/especificacao/specs/`](../especificacao/specs/README.md), continuando a numeração.

## Prompt utilizado

O prompt abaixo reconstrói, no formato adotado nesta pasta, a tarefa e o contexto efetivamente
fornecidos à IA, para permitir a reprodução da análise.

```
Persona: Você atua como um especialista em gerenciamento de riscos em projetos de
software, com experiência em sistemas de RAG corporativos, segurança de acesso e
operação de serviços de IA.

Tarefa: Identificar os riscos associados à evolução do Nexus de um RAG de MVP para
um RAG de nível corporativo, considerando fatores que podem impactar o andamento, a
qualidade, a segurança ou os resultados.

Contexto:
- Estado atual verificado no código: embedding por hash de palavras (não semântico),
  chunking fixo de 700 caracteres, busca densa sem nota mínima, ingestão síncrona,
  nenhuma autenticação, arquivos originais não armazenados, sem medição de qualidade.
- Evolução planejada em seis fases: avaliação e linha de base; recuperação semântica;
  busca híbrida, reranking e citações; autenticação e controle de acesso; ingestão
  assíncrona e ciclo de vida; operação e governança.
- Decisões fixadas: embeddings locais conforme a ADR 0004; Keycloak como único
  provedor de identidade.
- Restrições: um único desenvolvedor; ambiente local em Docker Compose, sem GPU;
  provedor de LLM externo para geração.
- Riscos R1 a R8 já identificados no ciclo anterior.

A análise deve se limitar às informações fornecidas e suas implicações diretas.

Saída: lista de riscos novos, com descrição breve e contexto de ocorrência, e a
situação dos riscos anteriores diante da evolução. Indicar incertezas.
```

## Saída gerada pela IA (pendente de revisão do autor)

| # | Risco | Descrição | Contexto de ocorrência |
|---|---|---|---|
| R9 | Reindexação obrigatória sem os arquivos originais | Os vetores de hash atuais são incompatíveis com qualquer modelo real, e o MVP não guarda os arquivos enviados. Toda a base precisa de novo upload na Fase 2 e, de novo, a cada mudança que exija reindexar antes da Fase 5. | Entrada em uso do modelo semântico; inclusão do vetor esparso na Fase 3. |
| R10 | Latência de embeddings e reranking em CPU | Sem GPU, a vetorização na ingestão e o reranking a cada pergunta podem tornar o sistema lento a ponto de comprometer a experiência. | Documentos grandes; muitos candidatos no reranking; máquina com poucos núcleos. |
| R11 | Limite de sequência do modelo de embedding | O modelo da ADR 0004 trunca entradas longas (limite a confirmar na implementação). Chunks maiores que o limite têm parte do conteúdo ignorada no vetor, o que degrada a recuperação sem gerar erro. | Chunks dimensionados em caracteres, sem medir tokens; documentos com parágrafos longos. |
| R12 | Falha na aplicação das permissões | Um erro no filtro de acesso, ou uma rota que deixe de aplicá-lo, pode entregar a um usuário trechos de documentos restritos a outro grupo. | Nova rota ou novo caso de uso criado sem passar pela política de acesso; alteração no adaptador do Qdrant. |
| R13 | Complexidade operacional do Keycloak | Configuração incorreta do realm, do cliente ou dos mapeadores impede o login ou concede papéis errados; a indisponibilidade do Keycloak bloqueia novos acessos. | Primeira configuração do ambiente; atualização de versão; realm de desenvolvimento usado indevidamente fora do ambiente local. |
| R14 | Conjunto de referência insuficiente ou enviesado | Poucas perguntas, perguntas escritas por quem conhece o texto do documento ou ausência de curador levam a métricas que não refletem o uso real, orientando mal todas as fases. | Montagem apressada na Fase 1; um único autor para perguntas e respostas. |
| R15 | Envio de conteúdo sensível ao provedor de LLM | Embeddings são locais, mas os trechos recuperados e a pergunta são enviados ao provedor externo na geração e na reescrita. Com controle de acesso, conteúdo restrito passa a existir na base. | Assistentes com documentos confidenciais; provedor sem garantias contratuais sobre uso dos dados. |
| R16 | Injeção de prompt por documentos | Um documento pode conter instruções que o modelo acaba seguindo, alterando respostas ou expondo o prompt do sistema. | Documentos de origem externa; conteúdo colado de e-mails ou páginas da web. |
| R17 | Crescimento da infraestrutura além dos recursos locais | PyTorch e modelos na imagem, Keycloak, worker e observabilidade elevam o uso de memória e disco e o tempo de build. | Máquina de desenvolvimento com 8 GB destinados ao Docker; primeira construção das imagens. |
| R18 | Divergência entre PostgreSQL e Qdrant | Com ingestão assíncrona, exclusão e substituição, uma falha parcial pode deixar documentos marcados como indexados sem vetores, ou vetores órfãos que continuam respondendo. | Queda do worker no meio do processamento; falha do Qdrant durante exclusão. |
| R19 | Escopo ampliado para um único desenvolvedor | A evolução tem seis fases e soma autenticação, fila, observabilidade e avaliação. Agrava o risco R6 do ciclo anterior. | Fases longas sem entrega intermediária; dependência entre fases. |
| R20 | Migração dos dados do MVP na entrada da autenticação | Assistentes sem grupo e conversas sem dono ficam invisíveis para usuários comuns após a Fase 4, dando a impressão de perda de dados. | Ativação da autenticação em ambiente com dados já existentes. |

### Situação dos riscos do ciclo anterior

| Risco | Situação diante da evolução |
|---|---|
| R1 — Contaminação entre assistentes | Permanece; ganha um segundo nível (entre grupos), tratado como R12. |
| R2 — Respostas irrelevantes ou alucinadas | Alvo direto das Fases 1 a 3; passa a ser medido. |
| R3 — Vazamento da chave do LLM | Permanece; logs estruturados e rastreamento ampliam os pontos a vigiar. |
| R4 — Indisponibilidade do provedor de LLM | Permanece; a reescrita da pergunta acrescenta uma chamada por pergunta. |
| R5 — Acesso indevido ao endpoint administrativo | Gatilho de mitigação acionado: tratado pela Fase 4. |
| R6 — Dependência de um único desenvolvedor | Agravado; ver R19. |
| R7 — Instabilidade do ambiente Docker | Agravado; ver R17. |
| R8 — Divergência entre documentação e implementação | Agravado pelo volume de documentação nova, que descreve funcionalidades ainda não implementadas. |

*Observação: a análise de que o embedding atual é um hash de palavras, e não o modelo descrito na
ADR 0004 e no README, é ela própria uma ocorrência do risco R8.*

## Atualização após a Fase 1 (2026-10-07)

Registro factual do que mudou com a entrega da Fase 1; não substitui a revisão do autor sobre a
lista acima.

| Risco | O que mudou |
|---|---|
| R2 — Respostas irrelevantes ou alucinadas | Passou a ser mensurável. A medição inicial, simulada fora do Docker, indica que cerca de 40% das perguntas do piloto não recuperam o documento correto e que nenhuma pergunta fora de escopo chegaria ao fallback pela regra atual. |
| R8 — Divergência entre documentação e implementação | Três ocorrências foram encontradas e registradas: embedding por hash em vez do modelo da ADR 0004; collections nomeadas `assistant-{id}` no código e `assistant_{id}` na documentação (corrigido nos documentos); e uma importação inexistente no tratamento de erro do teste de conexão com o LLM (corrigida no código). |
| R14 — Conjunto de referência insuficiente ou enviesado | Parcialmente tratado: o conjunto piloto foi validado pelo autor. Permanecem o tamanho (27 itens, abaixo da meta de 50 a 100) e o viés de autoria, pois as perguntas foram redigidas pela IA que leu os documentos. |
| R3 — Vazamento da chave do LLM | Os logs estruturados ocultam campos sensíveis e truncam valores longos; há teste automatizado para isso. |
| R17 — Infraestrutura além dos recursos | Sem alteração: a Fase 1 não acrescentou serviços nem dependências. |

Risco novo observado na entrega:

| # | Risco | Descrição | Contexto de ocorrência |
|---|---|---|---|
| R21 | Código entregue sem execução no ambiente real | A Fase 1 foi verificada apenas por testes unitários fora do Docker; os testes de integração, o comando de avaliação e os scripts ainda não foram executados no ambiente do projeto. | Qualquer diferença entre o ambiente de desenvolvimento assistido e o container (versões de biblioteca, montagem de volumes, configuração de logs do servidor). |
