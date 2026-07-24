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
