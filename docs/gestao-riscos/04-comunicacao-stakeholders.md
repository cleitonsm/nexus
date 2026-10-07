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

---

# Ciclo 2 — Evolução RAG Enterprise

## Prompt utilizado

Reconstruído no formato adotado nesta pasta.

```
Persona: Você atua como um gerente de projetos experiente em comunicação com
stakeholders não técnicos.

Tarefa: Elaborar uma comunicação sobre a evolução planejada do Nexus para um RAG
de nível corporativo, incluindo contexto, o que muda para as pessoas, riscos
identificados, decisões necessárias e próximos passos.

Contexto: o MVP está concluído. A evolução foi especificada em seis fases e ainda
não começou a ser implementada. Embeddings permanecem locais e o login será pelo
Keycloak. Principais riscos: proteção de conteúdo restrito, envio de trechos ao
provedor de IA, qualidade da medida e capacidade de um único desenvolvedor.

Saída esperada: texto claro, objetivo, com foco em tomada de decisão, sem jargão
técnico desnecessário.
```

## Saída gerada pela IA (pendente de revisão e ajuste do autor)

> **Assunto: Nexus — Proposta de evolução para uso corporativo**
>
> Olá,
>
> O Nexus concluiu sua primeira versão: já é possível criar assistentes, enviar documentos e
> conversar com eles. Compartilho agora a proposta do próximo ciclo, cujo objetivo é tornar o
> Nexus adequado para uso por diferentes áreas de uma organização.
>
> **Por que evoluir:** a versão atual tem três limites importantes. Ela só encontra a resposta
> quando a pergunta usa as mesmas palavras do documento; não mostra de onde a resposta veio; e
> não controla quem pode ver cada conteúdo.
>
> **O que muda para as pessoas:**
>
> - Quem pergunta poderá usar as próprias palavras e verá, em cada resposta, o documento e a
>   página de onde a informação saiu.
> - Cada pessoa entrará com sua conta e verá apenas os assistentes e documentos da sua área.
> - Quem cuida do conteúdo poderá atualizar, substituir e remover documentos sem interromper o uso.
> - Passaremos a medir, com números, se o assistente está respondendo bem.
>
> **Como será feito:** em seis etapas, cada uma utilizável por si só. As três primeiras tratam da
> qualidade das respostas; a quarta, do controle de acesso; as duas últimas, da gestão dos
> documentos e da operação. Nada foi implementado ainda: o que existe hoje é a especificação.
>
> **Riscos que precisam de atenção:**
>
> 1. **Proteção de conteúdo restrito.** Ao permitir documentos visíveis só para alguns grupos,
>    uma falha nesse controle teria impacto alto. Por isso ele terá testes automáticos próprios,
>    executados a cada mudança.
> 2. **Envio de trechos ao serviço de IA externo.** A preparação e a busca dos documentos
>    acontecem dentro do nosso ambiente, mas os trechos usados em cada resposta são enviados ao
>    serviço que redige o texto. É preciso confirmar se isso é aceitável para todo tipo de conteúdo.
> 3. **Qualidade da medida.** Os indicadores dependem de um conjunto de perguntas e respostas
>    preparado por quem conhece os documentos. Sem essa participação, os números enganam.
> 4. **Capacidade de execução.** O trabalho continua com um único desenvolvedor. As etapas foram
>    desenhadas para serem entregues uma a uma, com um ponto de reavaliação após a terceira.
>
> **Decisões que precisamos de vocês:**
>
> - Quem serão os responsáveis pelo conteúdo de cada assistente piloto.
> - Se algum conteúdo não pode ser enviado ao serviço de IA externo.
> - Se o controle por documento é necessário desde o início ou se o controle por assistente basta.
>
> **Próximos passos:** revisar e aprovar a especificação da primeira etapa, escolher o assistente
> piloto e preparar o conjunto inicial de perguntas.
>
> Fico à disposição para detalhar qualquer ponto.

## Ajustes do autor

Ainda não realizados. A comunicação acima é a versão gerada pela IA e deve ser revisada antes do
envio, como feito no ciclo anterior. Dois cuidados já aplicados na geração, em linha com os ajustes
do ciclo 1: evitar termos técnicos (embeddings, reranking, chunking) e manter os riscos de
segurança explícitos, sem atenuá-los.

## Atualização após a Fase 1 (2026-10-07)

Rascunho gerado pela IA, pendente de revisão do autor antes de qualquer envio.

> **Assunto: Nexus — Primeira etapa da evolução entregue**
>
> Olá,
>
> A primeira das seis etapas da evolução do Nexus foi concluída no código: agora conseguimos
> medir, com um comando, se o assistente encontra o documento certo e se responde de forma fiel ao
> que está escrito. Também passamos a conseguir acompanhar cada pergunta por todas as etapas do
> processamento.
>
> **O que a primeira medição mostra:** com a busca atual, cerca de 40% das perguntas de teste
> não localizam o documento correto, e perguntas fora do assunto não são recusadas como deveriam.
> Isso confirma a prioridade das duas próximas etapas, dedicadas à qualidade da busca.
>
> **Ressalvas:** a medição oficial ainda depende de executar a avaliação no ambiente completo, e o
> conjunto de perguntas de teste é pequeno (27 perguntas) e precisa crescer.
>
> **Decisão necessária:** aprovar a especificação da segunda etapa, que troca o mecanismo de busca
> e exige reenviar os documentos já carregados.
