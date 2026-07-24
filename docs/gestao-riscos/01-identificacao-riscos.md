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
