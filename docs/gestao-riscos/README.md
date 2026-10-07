# Gestão de Riscos e Comunicação — Atividade de Pós-Graduação

## Objetivo

Esta pasta reúne os artefatos produzidos na atividade prática da disciplina **Gerência de
Projetos de Software Apoiada por Inteligência Artificial Generativa** (Unidade III — Riscos,
Comunicação e Documentação Inteligente).

O exercício pede que o aluno utilize um Large Language Model (LLM) como apoio para conduzir as
etapas clássicas de gestão de riscos (identificação, análise qualitativa e definição de
estratégias de resposta) e para estruturar uma comunicação de status para stakeholders,
aplicando esses conceitos a um cenário — neste caso, um **projeto real**: o próprio Nexus.

## Cenário utilizado

Em vez do estudo de caso fictício proposto no curso (aplicativo de agendamento de consultas
médicas), optou-se por aplicar o exercício ao **Nexus**, projeto real desta pós-graduação: uma
plataforma RAG (Retrieval-Augmented Generation) para centralizar conhecimento organizacional em
assistentes conversacionais, construída em ciclos incrementais e documentada via ADRs (ver
[`docs/arquitetura/adrs`](../arquitetura/adrs) e [`docs/plano-incremental.md`](../plano-incremental.md)).

Optar por um projeto real, com decisões e restrições concretas já registradas, permitiu validar
os riscos gerados pela IA contra decisões arquiteturais que já haviam sido tomadas (e
documentadas em ADR), em vez de trabalhar apenas com hipóteses.

## Organização dos artefatos

| Arquivo | Conteúdo |
|---|---|
| [`01-identificacao-riscos.md`](01-identificacao-riscos.md) | Prompt utilizado e lista de riscos identificados com apoio de LLM, revisados pelo autor |
| [`02-analise-riscos.md`](02-analise-riscos.md) | Análise qualitativa (probabilidade x impacto) de cada risco e matriz consolidada |
| [`03-estrategias-resposta.md`](03-estrategias-resposta.md) | Estratégias de resposta (evitar, mitigar, transferir, aceitar) para os riscos priorizados |
| [`04-comunicacao-stakeholders.md`](04-comunicacao-stakeholders.md) | Comunicação de status elaborada com apoio de LLM para público não técnico |

Cada arquivo segue o mesmo padrão: **prompt estruturado (persona / tarefa / contexto / saída)** →
**saída gerada pelo modelo** → **revisão e ajustes feitos pelo autor**, deixando explícito o que
veio da IA e o que foi validado ou corrigido manualmente.

## Ferramenta de IA utilizada

Os artefatos foram elaborados com apoio do Cursor (agente de IA integrado ao IDE, com acesso de
leitura ao código e à documentação do próprio repositório Nexus), utilizando um modelo de
linguagem de grande porte (LLM) para gerar as primeiras versões de cada etapa a partir dos
prompts estruturados. Nenhuma informação sensível ou dado real de cliente foi utilizada — todo o
conteúdo é derivado da documentação pública do próprio projeto acadêmico.

## Ciclo 2 — Evolução RAG Enterprise

Além da atividade original, que cobre os riscos do MVP (R1 a R8), cada arquivo recebeu uma seção
**Ciclo 2**, dedicada aos riscos da evolução do Nexus para um RAG de nível corporativo (R9 a R20),
especificada em [`docs/especificacao/specs`](../especificacao/specs/README.md).

| Arquivo | Acréscimo do ciclo 2 |
|---|---|
| [`01-identificacao-riscos.md`](01-identificacao-riscos.md) | Riscos R9 a R20 e situação dos riscos R1 a R8 diante da evolução |
| [`02-analise-riscos.md`](02-analise-riscos.md) | Análise qualitativa e nova matriz de probabilidade x impacto |
| [`03-estrategias-resposta.md`](03-estrategias-resposta.md) | Estratégias sugeridas para R9, R11, R12, R14, R15 e R19 |
| [`04-comunicacao-stakeholders.md`](04-comunicacao-stakeholders.md) | Comunicação da proposta de evolução para público não técnico |

**Diferença importante em relação ao ciclo 1:** as seções do ciclo 2 contêm a saída gerada pela
IA **ainda sem a revisão do autor**. Os prompts foram reconstruídos no formato da pasta a partir
da tarefa e do contexto efetivamente fornecidos. As estratégias de resposta são sugestões; a
escolha final ainda não foi registrada. Ferramenta utilizada neste ciclo: Claude (Anthropic), em
modo agente, com acesso de leitura ao código e à documentação do repositório.

Cada arquivo traz ainda uma seção **Atualização após a Fase 1**, com o que mudou depois da
primeira entrega, incluindo o risco R21 (código entregue sem execução no ambiente real).

### Riscos de maior atenção no ciclo 2

- **R12** — falha na aplicação das permissões entre grupos.
- **R15** — envio de conteúdo sensível ao provedor de LLM.
- **R11** — limite de sequência do modelo de embedding, que degrada a busca sem gerar erro.
- **R14** — conjunto de referência insuficiente, que compromete todas as medidas.
