# Etapa 3 — Definição de Estratégias de Resposta

## Prompt utilizado

```
Persona: Você atua como um gerente de projetos com experiência em resposta a
riscos, com conhecimento em estratégias clássicas de tratamento de riscos em
projetos de software (evitar, mitigar, transferir, aceitar).

Tarefa: Sugerir estratégias de resposta para os riscos priorizados na matriz da
Etapa 2 (R1, R2, R3, R5, dado impacto Alto), explorando alternativas viáveis e
suas implicações, sem realizar uma escolha definitiva.

Contexto: os riscos foram identificados e analisados previamente, no contexto do
projeto Nexus. A análise servirá como apoio à tomada de decisão do autor.

Restrições: indicar claramente as limitações das sugestões; manter a análise em
nível exploratório e qualitativo.
```

## Saída gerada pela IA, com a escolha final validada pelo autor

### R1 — Contaminação de contexto entre assistentes

- **Evitar**: redesenhar para um único índice compartilhado eliminaria o risco, mas contradiz o princípio de produto de isolamento total (ADR 0003) — descartado.
- **Mitigar**: adicionar testes automatizados de integração que criem dois assistentes, indexem documentos distintos e validem que a busca de um nunca retorna chunks do outro; validar `assistant_id` em toda a cadeia (API → caso de uso → vector store).
- **Transferir**: não aplicável — é um risco interno à arquitetura do produto.
- **Aceitar**: aceitável apenas combinado com monitoramento (não isoladamente).

**Estratégia escolhida: Mitigar.** É o risco com maior impacto reputacional do produto (a promessa central do Nexus é "conhecimento isolado por assistente"), então vale investir em testes automatizados que rodem em toda alteração no fluxo de ingestão/busca, em vez de depender apenas de validação manual.

### R2 — Respostas irrelevantes/alucinadas por recuperação mal calibrada

- **Evitar**: não é possível evitar por completo — é uma limitação inerente ao padrão RAG.
- **Mitigar**: manter o fallback explícito ("não há evidência suficiente") já implementado no LangGraph, revisar periodicamente o tamanho de chunk e o threshold de relevância com casos de teste reais, e documentar exemplos de perguntas que expõem falhas de recuperação.
- **Transferir**: não aplicável.
- **Aceitar**: aceitar variações pontuais de qualidade é razoável para um MVP, desde que o fallback esteja ativo.

**Estratégia escolhida: Mitigar**, com o fallback como rede de segurança. Esse foi, aliás, o próprio ponto destacado como "uma das decisões mais importantes do produto" nas lições aprendidas do README: preferir honestidade a alucinação.

### R3 — Vazamento da API key do provedor de LLM

- **Evitar**: eliminar totalmente o uso de LLM externo (voltar a um modelo 100% local) reduziria a superfície de risco, mas atualmente não é viável para a qualidade de resposta esperada.
- **Mitigar**: manter a criptografia em repouso (já implementada), auditar logs para garantir que a chave nunca seja impressa, e restringir o retorno do valor da chave em qualquer endpoint (já é uma regra do ADR 0005) — reforçar com testes automatizados que garantam isso.
- **Transferir**: usar um secret manager gerenciado (ex.: cofre de segredos do provedor de nuvem) transferiria parte da responsabilidade de custódia da chave-mestra `NEXUS_SECRETS_KEY`.
- **Aceitar**: não recomendado como estratégia isolada, dado o impacto alto.

**Estratégia escolhida: Mitigar + Transferir.** Manter as práticas já implementadas (criptografia, não exposição via API) e, para além do MVP acadêmico, transferir a custódia da chave-mestra para um secret manager antes de qualquer uso em ambiente real de produção.

### R5 — Acesso indevido ao endpoint administrativo

- **Evitar**: não expor o endpoint fora de rede controlada — já é a premissa assumida no ADR 0005 para o MVP.
- **Mitigar**: adicionar uma camada mínima de autenticação (ex.: token administrativo simples) antes de qualquer demonstração fora do ambiente local controlado.
- **Transferir**: delegar o controle de acesso a um proxy/gateway (ex.: autenticação básica no Nginx/Traefik) sem alterar o código da aplicação.
- **Aceitar**: aceitável **apenas** enquanto o uso permanecer estritamente local/acadêmico, como o ADR já formaliza.

**Estratégia escolhida: Aceitar (no âmbito do MVP acadêmico), com gatilho explícito para Mitigar** — se o projeto avançar para uma demonstração pública ou uso real, a ausência de autenticação passa a ser inaceitável e a mitigação (autenticação mínima) deve ser implementada antes disso.

## Considerações gerais

- Riscos de impacto alto e baixa probabilidade (R1, R3) foram tratados priorizando **mitigação preventiva** (testes automatizados, práticas de segurança já existentes), já que o custo de corrigir depois de um incidente seria muito maior.
- O risco R5, apesar do impacto alto, foi conscientemente **aceito dentro de um limite claro** (uso local), refletindo o próprio raciocínio já documentado no ADR 0005 — um exemplo de como o apetite ao risco de um MVP acadêmico é diferente do de um produto em produção.
- Nenhuma estratégia foi aplicada apenas porque a IA sugeriu: cada escolha final considerou o estágio do projeto (MVP acadêmico) e as decisões arquiteturais já registradas nos ADRs.

---

# Ciclo 2 — Evolução RAG Enterprise

## Prompt utilizado

Reconstruído no formato adotado nesta pasta.

```
Persona: Você atua como um gerente de projetos com experiência em resposta a
riscos, com conhecimento em estratégias clássicas de tratamento de riscos em
projetos de software (evitar, mitigar, transferir, aceitar).

Tarefa: Sugerir estratégias de resposta para os riscos priorizados na matriz do
ciclo 2 (R11, R12, R14 e R15, de impacto Alto, e R9 e R19, de probabilidade Alta
e impacto Médio), explorando alternativas viáveis e suas implicações.

Contexto: evolução do Nexus para RAG de nível corporativo, com embeddings locais
(ADR 0004) e Keycloak como provedor de identidade.

Restrições: indicar claramente as limitações das sugestões; manter a análise em
nível exploratório e qualitativo.
```

## Saída gerada pela IA (estratégias sugeridas, pendentes de escolha do autor)

### R11 — Limite de sequência do modelo de embedding

- **Evitar**: trocar por um modelo local com limite maior eliminaria a restrição, mas altera o
  modelo definido na ADR 0004 e exige nova decisão registrada.
- **Mitigar**: medir os chunks com o tokenizador do próprio modelo, impedir configuração acima do
  limite e conferir o efeito na avaliação da Fase 1.
- **Transferir**: não aplicável.
- **Aceitar**: não recomendado; a degradação é silenciosa.

**Estratégia sugerida: Mitigar**, com gatilho para reavaliar o modelo se a meta de recall não for
atingida. É o que a SPEC-002 e a ADR 0006 especificam.

### R12 — Falha na aplicação das permissões

- **Evitar**: uma collection por grupo de acesso eliminaria o filtro, mas multiplicaria collections
  e duplicaria documentos compartilhados — descartado na ADR 0008.
- **Mitigar**: centralizar a regra no domínio, aplicar o filtro dentro da consulta ao vector
  store, negar por padrão e manter testes de integração recorrentes de acesso entre grupos.
- **Transferir**: não aplicável; a responsabilidade é do produto.
- **Aceitar**: inaceitável, dado o impacto.

**Estratégia sugerida: Mitigar**, tratando os testes de acesso como condição de conclusão de
qualquer mudança nas fases 4 a 6. Uma alternativa de redução de exposição é entregar primeiro
apenas o acesso por assistente e adiar a restrição por documento.

### R14 — Conjunto de referência insuficiente ou enviesado

- **Evitar**: não é possível avaliar sem conjunto de referência.
- **Mitigar**: exigir validação por curador, incluir perguntas fora do escopo e perguntas
  parafraseadas, revisar manualmente uma amostra dos julgamentos e alimentar o conjunto com
  respostas avaliadas como não úteis.
- **Transferir**: envolver curadores das áreas na autoria das perguntas.
- **Aceitar**: aceitar um conjunto pequeno no início é razoável, desde que cresça a cada fase.

**Estratégia sugerida: Mitigar + Transferir.** Começar pequeno, com perguntas escritas por quem
não redigiu os documentos, e ampliar continuamente.

### R15 — Envio de conteúdo sensível ao provedor de LLM

- **Evitar**: usar um modelo de geração local elimina o envio; a interface de LLM já permite
  apontar para um servidor compatível, com perda de qualidade de resposta a avaliar.
- **Mitigar**: enviar apenas os trechos necessários, dentro do orçamento de tokens; não registrar
  conteúdo em logs; permitir marcar assistentes que só podem usar modelo local.
- **Transferir**: firmar com o provedor garantias contratuais sobre retenção e uso dos dados.
- **Aceitar**: aceitável apenas para assistentes sem conteúdo confidencial.

**Estratégia sugerida: Mitigar + Transferir**, com a opção de Evitar por assistente. A decisão
depende da política de dados da organização e deve ser tomada antes da Fase 4.

### R9 — Reindexação obrigatória sem os arquivos originais

- **Evitar**: antecipar o armazenamento dos arquivos originais (parte da Fase 5) para antes da
  Fase 2 evita novos uploads nas fases seguintes.
- **Mitigar**: manter a base pequena e de teste até a Fase 5; documentar o procedimento de novo upload.
- **Transferir**: não aplicável.
- **Aceitar**: aceitável enquanto a base for de demonstração.

**Estratégia sugerida: Aceitar na Fase 2, com Evitar como alternativa** caso a base cresça antes
da Fase 5.

### R19 — Escopo ampliado para um único desenvolvedor

- **Evitar**: reduzir o escopo às Fases 1 a 3, que concentram o ganho de qualidade.
- **Mitigar**: manter cada fase entregável isoladamente, com especificação aprovada e critérios de
  conclusão próprios; reavaliar a prioridade ao fim de cada fase.
- **Transferir**: ampliar a equipe.
- **Aceitar**: aceitar prazos maiores, sem data fixa para a conclusão das seis fases.

**Estratégia sugerida: Mitigar**, com ponto de decisão explícito após a Fase 3.

## Considerações gerais

- Os dois riscos de maior impacto de segurança (R12 e R15) não podem ser aceitos; ambos pedem
  decisão antes do início da Fase 4.
- R11 e R14 afetam a validade das medidas; por isso a Fase 1 vem antes de todas as outras.
- As estratégias acima são **sugestões da IA**. A escolha final, como no ciclo anterior, cabe ao
  autor e ainda não foi registrada.

## Atualização após a Fase 1 (2026-10-07)

- **R14**: a estratégia sugerida (Mitigar + Transferir) começou a ser aplicada com a validação do
  conjunto piloto pelo autor. Próximos passos: ampliar para 50 a 100 itens e incluir perguntas
  escritas por quem não redigiu os documentos.
- **R21 — Mitigar**: executar no ambiente Docker os testes de integração e o comando de avaliação
  antes de marcar a SPEC-001 como implementada e antes de iniciar a Fase 2.
- **R9**: a alternativa de antecipar o armazenamento dos arquivos originais continua em aberto e
  deve ser decidida na aprovação da SPEC-002.
