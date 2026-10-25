# Escopo da Evolução RAG Enterprise

## Objetivo de Negócio

Levar o Nexus de uma demonstração de RAG em ambiente controlado para uma plataforma que uma
organização possa adotar com segurança: respostas mais precisas e verificáveis, acesso restrito a
quem pode ver cada conteúdo, base de conhecimento mantida atual e operação mensurável.

## Motivação

O MVP comprovou o ciclo completo, mas três limitações impedem o uso corporativo:

- **Precisão**: a busca só encontra trechos com as mesmas palavras da pergunta.
- **Segurança**: qualquer pessoa com acesso à rede lê e altera tudo.
- **Confiança**: as respostas não indicam a fonte e a qualidade não é medida.

## Dentro do Escopo

- Medição de qualidade com conjunto de referência validado por curadores.
- Embeddings semânticos locais, conforme a ADR 0004, e chunking por estrutura do documento.
- Busca híbrida, reranking local e fallback por nota mínima de relevância.
- Respostas com citação de documento, seção e página.
- Autenticação pelo Keycloak, com papéis de administrador, curador e usuário.
- Controle de acesso por assistente e por documento, com trilha de auditoria.
- Ingestão em segundo plano, com estado, exclusão, substituição e deduplicação de documentos.
- Leitura de PDFs digitalizados por OCR local.
- Observabilidade, custo estimado por conversa, limite de uso e backup.
- Resposta em streaming e avaliação da resposta pelo usuário.

## Fora do Escopo

- Multi-tenant completo, com isolamento entre organizações distintas.
- Outros provedores de identidade além do Keycloak.
- Embeddings, reranking ou OCR por serviços externos.
- Fine-tuning de modelos.
- Conectores automáticos a repositórios de documentos (drives, wikis, intranets).
- Fluxo formal de aprovação de respostas por especialistas.
- Painéis analíticos avançados de uso.
- Deploy em nuvem ou infraestrutura produtiva; a evolução continua validada em Docker local.

## Itens que Saem do "Fora do Escopo" do MVP

| Item fora do escopo no MVP | Situação na evolução |
|----------------------------|----------------------|
| Autenticação corporativa e controle granular de permissões | Dentro do escopo (Fase 4) |
| Painéis analíticos de uso | Parcial: consumo e custo por conversa (Fase 6) |
| Curadoria humana avançada | Parcial: papel de curador, conjunto de referência e feedback (Fases 1, 4 e 6) |
| Multi-tenant completo | Continua fora do escopo |
| Fine-tuning de modelos | Continua fora do escopo |
| Deploy em nuvem | Continua fora do escopo |

## Benefícios Esperados e Como Medir

| Benefício | Indicador | Meta inicial | Medido na validação final (2026-10-24) |
|-----------|-----------|--------------|------------------------------------------|
| Encontrar a informação certa | Recall@5 no conjunto de referência | Mínimo de 0,80 | 0,984 nas 3 execuções |
| Respostas fiéis aos documentos | Fidelidade ao contexto | Mínimo de 0,90 | 0,994 de média (0,983 a 1,0) |
| Não inventar quando não sabe | Fallback em perguntas fora do escopo | Mínimo de 90% | 90% nas 3 execuções |
| Resposta verificável | Respostas geradas com ao menos uma fonte | 100% | 100% |
| Conhecimento protegido | Trechos restritos recuperados por não autorizados | Zero nos testes | Zero (varredura com todos os usuários) |
| Curadoria sem espera | Tempo de resposta do upload | Até 2 segundos | Até 1,36 s (25 MB) |
| Operação previsível | Respostas rastreáveis de ponta a ponta | 100% | Um identificador por requisição em logs e spans (CT-44, CT-05) |

As metas foram mantidas após a linha de base; a medição é a da campanha `validacao-final-rc8`
([RESUMO](../qa/relatorios/2026-10-24-rc8/RESUMO.md)).

## Fases e Valor Entregue

| Fase | Entrega | Valor para o negócio | Situação |
|------|---------|----------------------|----------|
| 1 — Avaliação e linha de base | Conjunto de referência e relatório de qualidade | Decisões baseadas em medida, não em impressão | Validada (2026-10-24) |
| 2 — Recuperação semântica | Busca por significado | O usuário pergunta com as próprias palavras | Validada (2026-10-24) |
| 3 — Busca híbrida, reranking e citações | Fontes em cada resposta | O usuário confere e confia | Validada (2026-10-24) |
| 4 — Autenticação e controle de acesso | Login e permissões | O conteúdo sensível fica protegido | Validada (2026-10-24) |
| 5 — Ingestão e ciclo de vida | Base sempre atual | Documento desatualizado deixa de responder | Validada (2026-10-24) |
| 6 — Operação e governança | Visibilidade, custo e backup | O serviço pode ser sustentado | Validada (2026-10-24) |

### Andamento

Em 2026-10-07 a primeira fase foi entregue: já existe um comando que mede a qualidade das
respostas contra um conjunto de perguntas validado pelo responsável pelo conteúdo, e os registros
do sistema passaram a permitir acompanhar cada pergunta de ponta a ponta. A medição inicial
confirma a motivação desta evolução: com a busca atual, uma parte relevante das perguntas do
piloto não localiza o documento correto. Os números oficiais serão os da execução no ambiente completo.

Em 2026-10-08 o código das seis fases estava entregue e coberto por testes unitários, mas nenhuma
fase tinha sido validada no ambiente completo. A conclusão, com a comprovação das metas acima,
segue o [plano de conclusão](../plano-de-conclusao.md), com meta em 2026-11-19.

Em 2026-10-24 a campanha de validação final aprovou as seis fases no ambiente completo, com todas
as metas acima atingidas. Ficou uma limitação aceita: indexar um documento grande (10 MB, cerca de
300 páginas de texto) leva cerca de 2 minutos nesta máquina, acima do minuto previsto; a resposta
ao envio continua imediata, e a otimização fica para o próximo ciclo. Falta a verificação manual das
telas de ponta a ponta, depois da atualização de segurança do frontend.

## Critérios de Aceite da Evolução

- Um usuário só recebe respostas baseadas em documentos que seus grupos podem acessar.
- Toda resposta gerada a partir de documentos apresenta as fontes.
- Perguntas fora do escopo resultam em fallback explícito, sem chamada ao LLM.
- Excluir ou substituir um documento altera as respostas sem remover o assistente.
- As metas de qualidade são verificadas por um comando repetível.
- O ambiente completo, incluindo Keycloak e worker, sobe com um único comando.

## Premissas e Restrições

- Embeddings permanecem locais (ADR 0004).
- O provedor de identidade é sempre o Keycloak (ADR 0008).
- Os trechos recuperados continuam sendo enviados ao provedor de LLM configurado; isso precisa
  estar de acordo com a política de dados da organização.
- A evolução é conduzida por um único desenvolvedor, em fases independentes e validáveis.
- Dados usados em testes e na avaliação são fictícios ou públicos.

## Referências

- Especificações: [`docs/especificacao/specs/`](../especificacao/specs/README.md)
- Plano: [`docs/plano-incremental.md`](../plano-incremental.md), etapas 9 a 14
- Riscos: [`docs/gestao-riscos/`](../gestao-riscos/README.md), ciclo 2
