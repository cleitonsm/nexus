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
