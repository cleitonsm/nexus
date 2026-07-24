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
