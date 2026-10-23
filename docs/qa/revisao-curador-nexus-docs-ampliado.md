# Revisão do curador — `nexus-docs-ampliado` (55 rascunhos)

Gerado em 2026-10-20 para a validação exigida pela RN-15 (etapa EP do [plano de conclusão](../plano-de-conclusao.md)). Os 55 itens abaixo foram rascunhados por IA em 2026-10-14 e **só entram na avaliação oficial depois de aprovados por um curador humano**.

## Como revisar

Para cada item, confira três coisas:

1. **A pergunta** é clara e algo que um usuário perguntaria.
2. **A resposta esperada** está correta e completa segundo a fonte. A coluna "Trecho da fonte" traz a frase mais próxima, achada automaticamente; se ela não sustentar a resposta, abra o documento.
3. **A fonte** é o documento certo (nome do arquivo em `docs/negocio`, `docs/arquitetura` ou `backend/tests/evaluation/fixtures`).

Nos itens **fora do escopo**, confira que a base **não** responde à pergunta: o certo é o sistema recusar (fallback).

Itens com defeito: corrija a linha no `backend/tests/evaluation/datasets/nexus-docs-ampliado.jsonl` antes de aprovar, ou anote o id para eu corrigir. Depois:

```powershell
# aprova itens específicos (separe os ids por espaço)
python backend\tests\evaluation\validate_items.py backend\tests\evaluation\datasets\nexus-docs-ampliado.jsonl --by "Nome do curador" --approve te-01 te-02
# ou, depois de ler todos:
python backend\tests\evaluation\validate_items.py backend\tests\evaluation\datasets\nexus-docs-ampliado.jsonl --by "Nome do curador" --approve-all
# confere o que falta
python backend\tests\evaluation\validate_items.py backend\tests\evaluation\datasets\nexus-docs-ampliado.jsonl --list
```

## Pré-checagem automática

- **40 itens dentro do escopo:** todo arquivo de fonte citado existe na base, e todas as respostas têm de 75% a 100% dos termos presentes na fonte. Menor ancoragem, para olhar com mais cuidado: `te-11` (75%), `co-05` (82%), `co-09` (87%), `co-01` (89%), `co-02` (90%), `co-07` (91%).
- **15 itens fora do escopo.** Quatro são negativos "por pouco": a pergunta usa termos de um documento da base, mas pede algo que ele não tem. São bons testes, desde que a intenção seja o sistema recusar. Confirme cada um: `fora-08`; `fora-09`; `fora-10`; `fora-16`.
- A pré-checagem não substitui a leitura: ela só confere se as palavras da resposta aparecem na fonte, não se a resposta está certa.

## Termo exato (11)

| ok? | id | Pergunta | Resposta esperada | Fonte | Trecho da fonte |
|---|---|---|---|---|---|
| ☐ | `te-01` | O que significa a sigla RRF? | Reciprocal Rank Fusion: técnica que une os resultados de duas buscas pela posição de cada item. | glossario.md | técnica que une os resultados de duas buscas pela posição de |
| ☐ | `te-02` | Para que serve o vetor esparso BM25? | Encontrar correspondências exatas, como siglas e códigos, pela frequência de termos. | glossario.md, rag-e-isolamento-de-conhecimento.md | representação baseada na frequência de termos, usada para encontrar correspondências exatas, como siglas e códigos. - **Busca híbrida**: |
| ☐ | `te-03` | O que é OIDC no Nexus? | OpenID Connect, o protocolo de autenticação utilizado entre o Nexus e o Keycloak. | glossario.md | protocolo de autenticação utilizado entre o Nexus e o Keycloak. |
| ☐ | `te-04` | Qual ADR trata do filtro obrigatório por allowed_groups? | A ADR 0008. | rag-e-isolamento-de-conhecimento.md | filtro obrigatório por `allowed_groups`, aplicado na própria consulta ao Qdrant, com índice de payload (ADR 0008). O acesso ao assistente é verificado antes da busca. |
| ☐ | `te-05` | Como se chama a collection de um assistente no Qdrant? | assistant-{assistant_id}; é um alias para a versão vigente, e a collection física é assistant-{assistant_id}-v{n}. | rag-e-isolamento-de-conhecimento.md | assistant-{assistant_id} # alias para a versao vigente |
| ☐ | `te-06` | Quais requisitos definem as metas de recall, fidelidade e fallback? | Os requisitos RNF-19 a RNF-21. | rag-e-isolamento-de-conhecimento.md | requisitos RNF-19 a RNF-21, e qualquer mudança nesta estratégia deve ser acompanhada de nova |
| ☐ | `te-07` | Qual comando executa a avaliação de qualidade? | python -m src.cli.evaluate. | clean-architecture-backend.md | - **Ponto de entrada**: `python -m src.cli.evaluate`. As camadas de domínio e aplicação registram eventos apenas com a biblioteca padrão `logging`; |
| ☐ | `te-08` | O que significa a sigla SDD? | Spec-Driven Development: prática de aprovar a especificação antes de escrever o código. | glossario.md | prática de aprovar a especificação antes de escrever o código. |
| ☐ | `te-09` | Qual evento de log registra o uso do fallback? | chat.fallback.used. | langgraph-fluxo-conversacional.md | `chat.context.evaluated`, `chat.answer.generating` e `chat.fallback.used`, além dos |
| ☐ | `te-10` | Qual cabeçalho HTTP carrega o identificador da requisição? | X-Request-ID. | clean-architecture-backend.md | middleware que aceita, gera e devolve o cabeçalho `X-Request-ID`. |
| ☐ | `te-11` | Quantas dimensões tem o vetor denso e qual a métrica de similaridade? | 384 dimensões, com similaridade do cosseno. | rag-e-isolamento-de-conhecimento.md | / `dense` / 384 dimensões, cosseno / Modelo da ADR 0004, executado localmente / |

## Continuação (com histórico) (9)

| ok? | id | Pergunta | Resposta esperada | Fonte | Trecho da fonte |
|---|---|---|---|---|---|
| ☐ | `co-01` | E como os resultados das duas buscas são unidos?<br><small>Histórico: user: O que é busca híbrida? → assistant: É a combinação da busca por significado com a busca por termos exatos.</small> | Pela fusão RRF (Reciprocal Rank Fusion), que une os resultados pela posição de cada item. | glossario.md | técnica que une os resultados de duas buscas pela posição de |
| ☐ | `co-02` | E o que acontece com os trechos que ficam abaixo da nota dele?<br><small>Histórico: user: O que é reranking? → assistant: É uma segunda etapa de ordenação em que um modelo atribui uma nota de relevância a cada tr</small> | São descartados pela nota mínima de relevância; sem trechos acima dela, o assistente responde com o fallback. | glossario.md | sem trechos acima dela, o assistente responde com o fallback. - **Fallback**: |
| ☐ | `co-03` | E dentro do mesmo assistente?<br><small>Histórico: user: Como funciona o isolamento entre assistentes? → assistant: Cada assistente tem uma collection própria no Qdrant.</small> | Há um filtro obrigatório por allowed_groups, aplicado na própria consulta ao Qdrant. | rag-e-isolamento-de-conhecimento.md | filtro obrigatório por `allowed_groups`, aplicado na própria consulta |
| ☐ | `co-04` | O que a camada de infraestrutura implementa?<br><small>Histórico: user: Quais são as camadas do backend? → assistant: Domain, Application, Infrastructure e API.</small> | Os detalhes externos: persistência PostgreSQL, client Qdrant, geração local de embeddings, adapters de LLM e o grafo conversacional com LangGraph. | clean-architecture-backend.md | - adapters de LLM - grafo conversacional com LangGraph ### API |
| ☐ | `co-05` | Em que situações ele acontece?<br><small>Histórico: user: O que é o fallback? → assistant: É a resposta explícita de que a base não contém evidência suficiente.</small> | Quando nenhum trecho atinge a nota mínima de relevância ou quando a resposta gerada não traz citação válida. | glossario.md, langgraph-fluxo-conversacional.md | candidato e atribui uma nota de relevância. - **Nota mínima de relevância**: valor abaixo do qual um trecho é descartado; |
| ☐ | `co-06` | E qual é a meta mínima dele?<br><small>Histórico: user: Qual indicador mede se o trecho correto aparece entre os primeiros resultados? → assistant: O Recall@k.</small> | O Recall@5 mínimo é de 0,80. | escopo-rag-enterprise.md | / Encontrar a informação certa / Recall@5 no conjunto de referência / Mínimo de 0,80 / |
| ☐ | `co-07` | O que a fase 5 entrega?<br><small>Histórico: user: A evolução RAG Enterprise tem quantas fases? → assistant: Seis fases, da avaliação e linha de base até operação e governança.</small> | Ingestão e ciclo de vida, para que a base fique sempre atual: documento desatualizado deixa de responder. | escopo-rag-enterprise.md | / 5 — Ingestão e ciclo de vida / Base sempre atual / Documento desatualizado deixa de responder / Código entregue; |
| ☐ | `co-08` | Como a reindexação o utiliza?<br><small>Histórico: user: O que é um alias no Qdrant? → assistant: É um nome estável que aponta para a versão vigente de uma collection.</small> | Ela cria a versão seguinte da collection, confere as contagens e troca o alias de forma atômica. | rag-e-isolamento-de-conhecimento.md, glossario.md | A reindexação cria a versão seguinte, confere as contagens e troca o alias de forma atômica. |
| ☐ | `co-09` | Em que etapa da ingestão ele entra?<br><small>Histórico: user: O que é o worker de ingestão? → assistant: É o processo que trata os documentos em segundo plano.</small> | Depois que o documento é enfileirado e o usuário recebe a resposta: no worker ele extrai o texto estruturado, fragmenta, gera os vetores e grava na collection. | rag-e-isolamento-de-conhecimento.md | 5. Gravar vetores e metadados na collection do assistente. ## Metadados Mínimos por Chunk |

## Tabelas de DOCX (9)

| ok? | id | Pergunta | Resposta esperada | Fonte | Trecho da fonte |
|---|---|---|---|---|---|
| ☐ | `tb-01` | Qual é a diária nacional de um Coordenador? | R$ 350. | politica-viagens.docx | Analista / R$ 250 / US$ 120 Coordenador / R$ 350 / US$ 180 Gerente / R$ 480 / US$ 260 |
| ☐ | `tb-02` | Qual é a diária internacional de um Diretor? | US$ 400. | politica-viagens.docx | Gerente / R$ 480 / US$ 260 Diretor / R$ 700 / US$ 400 Tipo de viagem / Prazo |
| ☐ | `tb-03` | Qual é o prazo de prestação de contas de uma viagem internacional? | 10 dias úteis. | politica-viagens.docx | Nacional / 5 dias úteis Internacional / 10 dias úteis Evento corporativo / 3 dias úteis |
| ☐ | `tb-04` | Qual cargo tem diária nacional de R$ 480? | Gerente. | politica-viagens.docx | Coordenador / R$ 350 / US$ 180 Gerente / R$ 480 / US$ 260 Diretor / R$ 700 / US$ 400 |
| ☐ | `tb-05` | Quanto é o vale-refeição de quem tem mais de 3 anos de casa? | R$ 45 por dia. | beneficios-e-suporte.docx | De 1 a 3 anos / R$ 38 por dia / 80% de cobertura Acima de 3 anos / R$ 45 por dia / 90% de cobertura Canal / Horário / Prazo de resposta |
| ☐ | `tb-06` | Qual é a cobertura do auxílio-saúde para quem tem de 1 a 3 anos de casa? | 80% de cobertura. | beneficios-e-suporte.docx | Até 1 ano / R$ 32 por dia / 70% de cobertura De 1 a 3 anos / R$ 38 por dia / 80% de cobertura Acima de 3 anos / R$ 45 por dia / 90% de cobertura |
| ☐ | `tb-07` | Qual é o horário do suporte por telefone? | Das 8h às 20h. | beneficios-e-suporte.docx | Chat / 8h às 18h / 15 minutos Telefone / 8h às 20h / 30 minutos E-mail / 24 horas / 1 dia útil |
| ☐ | `tb-08` | Qual é o prazo de resposta do suporte por e-mail? | 1 dia útil. | beneficios-e-suporte.docx | Telefone / 8h às 20h / 30 minutos E-mail / 24 horas / 1 dia útil |
| ☐ | `tb-09` | Em quantos dias úteis deve ser feita a prestação de contas de um evento corporativo? | 3 dias úteis. | politica-viagens.docx | Internacional / 10 dias úteis Evento corporativo / 3 dias úteis |

## Pipeline e arquitetura (11)

| ok? | id | Pergunta | Resposta esperada | Fonte | Trecho da fonte |
|---|---|---|---|---|---|
| ☐ | `pl-01` | O que é uma fonte oficial? | Um documento enviado e aceito como base de conhecimento de um assistente. | glossario.md | documento enviado e aceito como base de conhecimento de um assistente. |
| ☐ | `pl-02` | O que é chunking estrutural? | A divisão do documento respeitando títulos, parágrafos e tabelas. | glossario.md | divisão do documento respeitando títulos, parágrafos e tabelas. |
| ☐ | `pl-03` | O que é injeção de prompt? | A tentativa de fazer o assistente obedecer a instruções escondidas em um documento. | glossario.md | tentativa de fazer o assistente obedecer a instruções escondidas em um documento. |
| ☐ | `pl-04` | O Nexus vai fazer fine-tuning de modelos? | Não. O fine-tuning de modelos está fora do escopo da evolução. | escopo-rag-enterprise.md | / Multi-tenant completo / Continua fora do escopo / / Fine-tuning de modelos / Continua fora do escopo / / Deploy em nuvem / Continua fora do escopo / |
| ☐ | `pl-05` | Quais limitações do MVP motivaram a evolução RAG Enterprise? | Precisão (a busca só encontra as mesmas palavras), segurança (qualquer pessoa com acesso à rede lê e altera tudo) e confiança (as respostas não indicam a fonte e a qualidade não é medida). | escopo-rag-enterprise.md | - **Segurança**: qualquer pessoa com acesso à rede lê e altera tudo. - **Confiança**: |
| ☐ | `pl-06` | Qual é a meta mínima de fidelidade ao contexto? | Mínimo de 0,90. | escopo-rag-enterprise.md | / Respostas fiéis aos documentos / Fidelidade ao contexto / Mínimo de 0,90 / |
| ☐ | `pl-07` | Que papéis de usuário existem no Nexus? | Administrador, curador e usuário. | glossario.md, escopo-rag-enterprise.md | função do usuário no Nexus — administrador, curador ou usuário. |
| ☐ | `pl-08` | O que acontece com uma resposta gerada sem citação válida? | Ela é substituída pelo fallback. | langgraph-fluxo-conversacional.md | uma resposta sem citação válida é substituída pelo fallback. |
| ☐ | `pl-09` | O que a etapa de reescrita da pergunta faz quando não há histórico? | É ignorada. | langgraph-fluxo-conversacional.md | transforma perguntas de continuação em consultas autônomas; ignorada quando não há histórico. |
| ☐ | `pl-10` | Por que o MVP não usa collections compartilhadas entre assistentes? | Porque isso aumenta o risco de mistura de contexto; a collection própria torna o isolamento simples e fácil de testar. | rag-e-isolamento-de-conhecimento.md | Essa alternativa não é necessária para o MVP e aumenta o risco de mistura de contexto. ## Evolução RAG Enterprise |
| ☐ | `pl-11` | O que é a tolerância de regressão? | A queda máxima aceita em um indicador entre duas avaliações; acima dela a mudança é reprovada. | glossario.md | - **Tolerância de regressão**: queda máxima aceita em um indicador entre duas avaliações; acima |

## Fora do escopo (o sistema deve recusar) (15)

| ok? | id | Pergunta | Observação |
|---|---|---|---|
| ☐ | `fora-06` | Qual é a capital da Austrália? | |
| ☐ | `fora-07` | Como configurar uma VPN corporativa no Linux? | |
| ☐ | `fora-08` | Qual é o limite de diária para um estagiário? | negativo por pouco: politica-viagens.docx tem tema parecido, mas não responde |
| ☐ | `fora-09` | Qual é o prazo de resposta do suporte por WhatsApp? | negativo por pouco: beneficios-e-suporte.docx tem tema parecido, mas não responde |
| ☐ | `fora-10` | Qual é o valor do vale-transporte da empresa? | negativo por pouco: visao-produto.md tem tema parecido, mas não responde |
| ☐ | `fora-11` | Qual é o salário médio de um analista pleno? | |
| ☐ | `fora-12` | Como fazer um bolo de cenoura? | |
| ☐ | `fora-13` | Quem venceu a Copa do Mundo de 2014? | |
| ☐ | `fora-14` | Qual é a cotação do dólar hoje? | |
| ☐ | `fora-15` | Como redefinir a senha do e-mail corporativo? | |
| ☐ | `fora-16` | Qual é o prazo de prestação de contas para viagens de capacitação? | negativo por pouco: politica-viagens.docx tem tema parecido, mas não responde |
| ☐ | `fora-17` | Quantos dias de licença-paternidade a empresa oferece? | |
| ☐ | `fora-18` | Qual é o horário de funcionamento do refeitório? | |
| ☐ | `fora-19` | Quantos funcionários a empresa possui? | |
| ☐ | `fora-20` | Qual é o procedimento de evacuação em caso de incêndio no prédio? | |
