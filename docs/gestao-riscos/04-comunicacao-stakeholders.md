# Etapa 4 — Comunicação para Stakeholders

## Prompt utilizado

```
Persona: Você atua como um gerente de projetos experiente em comunicação com
stakeholders não técnicos, com habilidade para traduzir informações técnicas em
linguagem acessível, sem perder precisão.

Tarefa: Elaborar uma comunicação de status do projeto Nexus para um público não
técnico (orientador/banca acadêmica), incluindo contexto, riscos identificados,
ações em andamento e próximos passos. Não apenas descrever problemas — estruturar
uma narrativa.

Contexto: o projeto está em fase de consolidação do MVP (etapas 6-8 do plano
incremental: fluxo conversacional, frontend e integração E2E). Os principais riscos
identificados são: qualidade das respostas do RAG, segurança da chave de LLM e
dependência de um único desenvolvedor com prazo fixo.

Saída esperada: texto claro, objetivo, com foco em tomada de decisão, sem jargão
técnico desnecessário.
```

## Saída gerada pela IA (revisada e ajustada pelo autor)

> **Assunto: Status do Projeto Nexus — Consolidação do MVP e Riscos em Acompanhamento**
>
> Olá,
>
> Compartilho um resumo do andamento do Nexus, projeto de pós-graduação que propõe um
> assistente conversacional capaz de responder perguntas com base em documentos
> oficiais de uma organização, em vez de depender apenas do conhecimento genérico de
> um modelo de linguagem.
>
> **Onde estamos:** as etapas de fundação (documentação, ambiente, domínio,
> persistência e ingestão de documentos) já foram concluídas e validadas. Estamos
> agora consolidando o fluxo de conversa entre o usuário e o assistente, e
> finalizando a integração entre a interface web e o backend.
>
> **O que está funcionando bem:** cada assistente mantém sua própria base de
> conhecimento isolada — perguntas sobre o assistente A nunca retornam informações
> do assistente B. Isso já foi testado com dois assistentes distintos e é um dos
> pilares de confiança do produto.
>
> **Riscos que estamos acompanhando de perto:**
>
> 1. **Qualidade das respostas.** Como o assistente busca trechos de documentos
>    antes de responder, a qualidade depende de como esses documentos foram
>    divididos internamente. Quando não há trecho relevante suficiente, o sistema
>    foi projetado para admitir isso explicitamente, em vez de inventar uma
>    resposta — essa é uma decisão deliberada de produto, não uma falha.
> 2. **Segurança da credencial do provedor de IA externo.** A chave de acesso ao
>    modelo de linguagem é armazenada de forma criptografada e nunca é exposta pela
>    aplicação. Ainda assim, o painel administrativo que a configura não possui
>    autenticação própria nesta fase — por isso, o projeto continua restrito a
>    ambiente controlado (não deve ser exposto publicamente sem esse ajuste).
> 3. **Dependência de um único desenvolvedor.** Por ser um projeto individual com
>    prazo acadêmico fixo, qualquer imprevisto de agenda tem impacto direto no
>    cronograma. Para reduzir esse risco, o trabalho foi dividido em etapas
>    pequenas e validáveis de forma independente, garantindo que exista sempre uma
>    versão funcional entregável, mesmo que incompleta.
>
> **Próximos passos:** concluir a integração entre interface e backend, validar o
> ciclo completo (criar assistente → enviar documento → perguntar → obter resposta
> rastreável) e registrar as lições aprendidas para a entrega final.
>
> Seguimos disponíveis para qualquer esclarecimento ou ajuste de prioridades.

## Ajustes feitos pelo autor em relação à saída original da IA

- A primeira versão gerada pela IA usava o termo "chunking" mesmo no texto destinado ao
  público não técnico; foi reescrito como "como esses documentos foram divididos
  internamente".
- A IA havia sugerido omitir o risco de segurança do endpoint administrativo "para não
  gerar alarme". Optou-se por manter o risco explícito, de forma transparente, pois
  ocultar riscos conhecidos do stakeholder contraria o princípio de comunicação honesta
  discutido no material do curso.
- Foi adicionada a frase final oferecendo disponibilidade para ajuste de prioridades,
  ausente na versão gerada, para reforçar o caráter colaborativo da comunicação.
