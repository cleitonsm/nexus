# Etapa 2 — Análise dos Riscos

## Prompt utilizado

```
Persona: Você atua como um analista de riscos em projetos de software, com
experiência na análise qualitativa de riscos e aplicação de matrizes de
probabilidade e impacto.

Tarefa: Realizar uma análise estruturada dos riscos previamente identificados
(R1-R8), descrevendo impactos e fatores associados, e organizá-los em uma matriz
qualitativa de probabilidade x impacto.

Contexto: os riscos já foram identificados na Etapa 1, no contexto do projeto Nexus
(plataforma RAG acadêmica, MVP em ciclos incrementais, um único desenvolvedor).

Restrições: não atribuir valores numéricos de probabilidade ou impacto; indicar
incertezas quando necessário.
```

## Saída gerada pela IA (revisada pelo autor)

| Risco | Possíveis impactos no projeto | Fatores que influenciam a ocorrência | Probabilidade | Impacto | Justificativa |
|---|---|---|---|---|---|
| R1 — Contaminação de contexto entre assistentes | Perda de confiança no produto; respostas incoerentes; necessidade de reindexação completa | Robustez dos testes de isolamento; frequência de criação/exclusão de assistentes | Baixa | Alto | O isolamento por collection (ADR 0003) é simples e já foi validado com dois assistentes distintos no plano incremental, mas o impacto de uma falha é grave por comprometer o pilar central do produto (confiabilidade da resposta). |
| R2 — Respostas irrelevantes/alucinadas | Redução da utilidade percebida do MVP; necessidade de reajustar chunking e thresholds | Qualidade dos documentos de teste; calibração do LangGraph | Média | Alto | O próprio README do projeto reconhece que "RAG não é mágico — é um contrato"; é um risco estrutural do padrão RAG, não específico de um bug. |
| R3 — Vazamento da API key do provedor de LLM | Uso indevido da chave, custos inesperados, exposição de terceiros | Qualidade do tratamento de exceções; nível de verbosidade de logs | Baixa | Alto | A criptografia em repouso (ADR 0005) reduz a probabilidade, mas o impacto de um vazamento continua alto por envolver credencial de terceiro. |
| R4 — Indisponibilidade/mudança do provedor de LLM | Interrupção do chat; necessidade de troca de adapter sob pressão | Dependência de serviço externo fora do controle do time | Média | Médio | O adapter de LLM é configurável por variável de ambiente (troca sem alterar domínio), o que reduz o impacto em relação a uma integração fortemente acoplada. |
| R5 — Acesso indevido ao endpoint administrativo | Alteração ou exposição indevida da configuração da API key | Ausência de autenticação nesta fase do MVP (ADR 0005 explicita essa limitação) | Média | Alto | O próprio ADR já assume esse risco como aceito para o MVP, condicionado a rede controlada — mas qualquer exposição fora desse ambiente eleva o impacto. |
| R6 — Atraso por dependência de um único desenvolvedor | Entrega parcial do MVP; corte de escopo sob pressão de prazo | Carga de trabalho concorrente do aluno; complexidade subestimada de alguma etapa | Média | Médio | Mitigado parcialmente pela divisão em 8 etapas incrementais com critérios de validação próprios (plano incremental), o que permite entregar valor parcial mesmo sob atraso. |
| R7 — Instabilidade do ambiente Docker local | Bloqueio da validação manual; retrabalho de configuração | Recursos de hardware disponíveis; conflitos de porta com outros serviços locais | Alta | Baixo | Já é um risco conhecido e documentado no `troubleshooting.md`, com causas e soluções mapeadas — impacto limitado por ser rapidamente diagnosticável. |
| R8 — Divergência entre documentação e implementação | Decisões antigas deixam de refletir o estado real do sistema, gerando confusão em revisões futuras | Volume de mudanças por ciclo incremental; disciplina de atualizar ADRs | Média | Baixo | O impacto é mais organizacional/acadêmico (qualidade da documentação) do que funcional, já que o sistema continua operando independentemente da documentação. |

## Matriz Qualitativa de Riscos

| Probabilidade \ Impacto | Baixo | Médio | Alto |
|---|---|---|---|
| **Alta** | R7 | | |
| **Média** | R8 | R4, R6 | R2, R5 |
| **Baixa** | | | R1, R3 |

*Nota: como recomendado no material do curso, a classificação é qualitativa e não deve ser interpretada como medição precisa — trata-se de um apoio à priorização, validado pelo autor a partir do conhecimento do projeto real, e não uma saída aceita "as-is" da IA.*

---

# Ciclo 2 — Evolução RAG Enterprise

## Prompt utilizado

Reconstruído no formato adotado nesta pasta.

```
Persona: Você atua como um analista de riscos em projetos de software, com
experiência na análise qualitativa de riscos e aplicação de matrizes de
probabilidade e impacto.

Tarefa: Realizar uma análise estruturada dos riscos R9 a R20, descrevendo impactos
e fatores associados, e organizá-los em uma matriz qualitativa de probabilidade x
impacto.

Contexto: riscos identificados no ciclo 2, referentes à evolução do Nexus para um
RAG de nível corporativo, com embeddings locais, Keycloak, um único desenvolvedor
e ambiente local sem GPU.

Restrições: não atribuir valores numéricos de probabilidade ou impacto; indicar
incertezas quando necessário.
```

## Saída gerada pela IA (pendente de revisão do autor)

| Risco | Possíveis impactos no projeto | Fatores que influenciam a ocorrência | Probabilidade | Impacto | Justificativa |
|---|---|---|---|---|---|
| R9 — Reindexação sem originais | Retrabalho de upload; base indisponível durante a migração | Quantidade de documentos já carregados; ordem das fases | Alta | Médio | É certo que ocorrerá na Fase 2; o impacto é limitado enquanto a base for pequena e de teste. |
| R10 — Latência em CPU | Respostas lentas; ingestão demorada; descumprimento do RNF-16 | Número de candidatos no reranking; tamanho do modelo; hardware | Média | Médio | Controlável por configuração; a medida da Fase 1 permite detectar cedo. |
| R11 — Limite de sequência do modelo | Recuperação degradada de forma silenciosa; meta de recall não atingida | Tamanho do chunk; uso do tokenizador do modelo | Alta | Alto | Sem medir em tokens, o problema ocorre e não gera erro; afeta o objetivo central da Fase 2. |
| R12 — Falha nas permissões | Exposição de conteúdo restrito; perda de confiança; possível incidente de conformidade | Cobertura de testes de acesso; disciplina de passar pela política de acesso | Baixa | Alto | A política centralizada no domínio reduz a probabilidade; o impacto é o mais grave da evolução. |
| R13 — Complexidade do Keycloak | Login indisponível; papéis incorretos; tempo gasto em configuração | Experiência prévia; realm versionado; versão fixada | Média | Médio | Ferramenta madura, mas com muitas opções de configuração; o realm importado na subida reduz a variação. |
| R14 — Conjunto de referência fraco | Métricas enganosas; decisões erradas em todas as fases | Disponibilidade de curador; diversidade das perguntas | Média | Alto | Todo o plano depende dessa medida; um conjunto ruim invalida as conclusões sem que isso seja percebido. |
| R15 — Conteúdo sensível no LLM externo | Exposição de dados a terceiros; restrição de uso pela área de segurança | Natureza dos documentos; garantias do provedor | Média | Alto | Passa a existir conteúdo restrito na base; o envio ao provedor é inerente à geração. |
| R16 — Injeção de prompt | Respostas manipuladas; exposição do prompt do sistema | Origem dos documentos; robustez do modelo | Baixa | Médio | Documentos são enviados por curadores autenticados; a proteção reduz, mas não elimina. |
| R17 — Infraestrutura além dos recursos | Ambiente instável; build lento; validação bloqueada | Memória disponível; quantidade de serviços ativos | Alta | Baixo | Já previsto na documentação de infraestrutura (12 GB confortáveis); diagnosticável rapidamente. |
| R18 — Divergência PostgreSQL × Qdrant | Documento removido que continua respondendo; documento "indexado" sem resultados | Idempotência do worker; rotina de conferência | Média | Médio | Não há transação entre os dois sistemas; o efeito é localizado e corrigível por reprocessamento. |
| R19 — Escopo para um desenvolvedor | Fases incompletas; corte de escopo; atraso | Carga concorrente; tamanho das fases | Alta | Médio | Seis fases com dependência entre si; mitigado por cada fase ser entregável isoladamente. |
| R20 — Migração de dados na autenticação | Assistentes e conversas "desaparecem" para usuários | Existência de dados anteriores; comunicação prévia | Média | Baixo | Os dados não são perdidos, apenas ocultos; resolvido por configuração de grupos. |

## Matriz Qualitativa de Riscos (Ciclo 2)

| Probabilidade \ Impacto | Baixo | Médio | Alto |
|---|---|---|---|
| **Alta** | R17 | R9, R19 | R11 |
| **Média** | R20 | R10, R13, R18 | R14, R15 |
| **Baixa** | | R16 | R12 |

*Nota: classificação qualitativa, gerada pela IA a partir da leitura do código e das
especificações. Não foi validada pelo autor e não deve ser lida como medição precisa.*

## Atualização após a Fase 1 (2026-10-07)

| Risco | Probabilidade | Impacto | Justificativa |
|---|---|---|---|
| R14 — Conjunto de referência fraco | Média | Alto | Mantida: a validação pelo autor reduz o risco de itens errados, mas o conjunto segue pequeno e com viés de autoria. |
| R21 — Código sem execução no ambiente real | Média | Baixo | A lógica central está coberta por testes unitários; falhas prováveis seriam de configuração, diagnosticáveis na primeira execução. |

Classificação sugerida pela IA, pendente de revisão do autor.
