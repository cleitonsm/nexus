# Especificação de Requisitos — Nexus

Esta pasta contém os artefatos de especificação produzidos na atividade prática da disciplina
**Engenharia de Requisitos com Inteligência Artificial Generativa**.

---

## Estrutura

| Arquivo | Conteúdo |
|---------|----------|
| `requisitos-funcionais.md` | 23 requisitos funcionais organizados por módulo (Assistentes, Documentos, Chat, LLM, Interface). |
| `requisitos-nao-funcionais.md` | 15 requisitos não funcionais nas categorias Desempenho, Segurança, Isolamento, Portabilidade, Manutenibilidade e Usabilidade. |
| `regras-de-negocio.md` | 13 regras de negócio que restringem ou condicionam os requisitos funcionais. |
| `historias-de-usuario.md` | 14 histórias de usuário organizadas em 6 épicos. |
| `criterios-de-aceitacao.md` | Critérios Given–When–Then para cada história relevante, mais critérios de integração do MVP. |
| `casos-de-uso.md` | 5 casos de uso descrevendo os fluxos principais e alternativos do sistema. |
| `estrategia-de-testes.md` | Níveis de teste e 48 casos de teste (CT-01 a CT-48) da evolução RAG Enterprise. |
| `specs/` | Seis especificações SDD, uma por fase da evolução RAG Enterprise. |

Cada arquivo de requisitos, regras, histórias, critérios e casos de uso possui duas partes: o
conteúdo do **MVP** e a seção **Evolução — RAG Enterprise**, que continua a mesma numeração.

| Artefato | MVP | Evolução RAG Enterprise | Total |
|----------|-----|-------------------------|-------|
| Requisitos funcionais | RF-01 a RF-23 | RF-24 a RF-63 | 63 |
| Requisitos não funcionais | RNF-01 a RNF-15 | RNF-16 a RNF-33 | 33 |
| Regras de negócio | RN-01 a RN-13 | RN-14 a RN-33 | 33 |
| Histórias de usuário | HU-01 a HU-14 (épicos 1 a 6) | HU-15 a HU-37 (épicos 7 a 12) | 37 |
| Casos de uso | UC-01 a UC-05 | UC-06 a UC-13 | 13 |

---

## Artefatos Escolhidos e Justificativa

### Por que Histórias de Usuário + Critérios de Aceitação?

O Nexus é um produto de software desenvolvido de forma incremental, seguindo práticas próximas
de metodologias ágeis. As histórias de usuário são o formato mais adequado para capturar valor
de negócio de maneira simples e centrada no usuário final. Complementá-las com critérios de
aceitação no formato Dado–Quando–Então (BDD) garante que cada história seja verificável
objetivamente — respondendo à exigência de *requisitos verificáveis* conforme ISO/IEC/IEEE 29148.

### Por que Casos de Uso?

Os cinco fluxos principais do sistema (criar assistente, ingerir documento, conversar, inferir
assistente, configurar LLM) envolvem atores e interações suficientemente complexas — incluindo
fluxos alternativos e pós-condições — para justificar o formato estruturado de casos de uso.
Esse artefato facilita a comunicação com a equipe técnica e serve de base para testes de
aceitação de ponta a ponta.

### Por que Requisitos Funcionais + Não Funcionais + Regras de Negócio separados?

A separação explícita desses três elementos elimina ambiguidades frequentes (ex.: o que é
comportamento do sistema vs. restrição organizacional vs. atributo de qualidade). Isso
facilita a rastreabilidade — cada história de usuário referencia RFs, que por sua vez apontam
para RNFs e RNs relacionadas.

### O que foi descartado

- **Protótipos formais:** a interface já existe em código Angular; capturas de tela do sistema
  funcionando suprem essa necessidade sem duplicar esforço.
- **Diagrama de casos de uso UML:** o volume de casos de uso é pequeno (5), tornando o
  diagrama pouco informativo. Os casos de uso textuais são suficientes.
- **Documento de Requisitos (SRS) completo:** o contexto ágil e incremental do projeto favorece
  artefatos menores e evoluíveis em vez de um documento monolítico.

---

## Como a IA Generativa apoiou esta atividade

**Ferramenta utilizada:** Claude (Anthropic), acessado via Cursor IDE (modo agente).

### Sugestões aproveitadas

1. **Separação em módulos dos requisitos funcionais** — a IA sugeriu organizar os RFs por
   módulo funcional (Assistentes, Documentos, Chat, LLM, Interface), o que facilita leitura
   e rastreabilidade. Adotado integralmente.

2. **Estrutura Given–When–Then para critérios de aceitação** — a IA propôs o uso de BDD para
   tornar os critérios verificáveis objetivamente, alinhado ao conceito de *requisito verificável*
   da ISO/IEC/IEEE 29148. Adotado integralmente.

3. **Identificação de requisitos não funcionais implícitos** — durante a análise, a IA apontou
   que os documentos de negócio do Nexus mencionavam isolamento de bases e criptografia, mas
   não os explicitavam como RNFs formais. Essa sugestão foi validada contra o código existente
   (ADRs em `docs/arquitetura/adrs/`) e incorporada.

4. **Fluxos alternativos dos casos de uso** — a IA sugeriu cenários de exceção como timeout
   do LLM, formato de arquivo não suportado e inferência retornando `null`. Todos alinhados
   com comportamentos já implementados no sistema.

### Sugestões modificadas

1. **Critérios de desempenho** — a IA sugeriu limites genéricos (ex.: "2 segundos para qualquer
   operação"). Esses valores foram ajustados para refletir a realidade do sistema: operações de
   LLM têm latências maiores que operações locais, e o limite de 30 s para o primeiro token é
   mais realista para provedores externos.

2. **Histórias de usuário para multi-tenant e autenticação** — a IA gerou histórias sobre
   controle granular de permissões e login corporativo. Essas histórias foram descartadas, pois
   tais funcionalidades estão explicitamente fora do escopo do MVP
   (ver `docs/negocio/escopo-mvp.md`).

3. **Caso de uso de "Gerenciar usuários"** — sugerido pela IA mas removido pelos mesmos motivos
   acima (fora do escopo do MVP).

### Sugestões descartadas

1. **Diagrama de sequência UML gerado em Mermaid** — a IA propôs gerar diagramas UML para cada
   caso de uso. Descartado porque o repositório já contém diagramas C4 e de fluxo LangGraph que
   cobrem a arquitetura, e duplicar essa informação em UML aumentaria a carga de manutenção sem
   adicionar valor.

2. **Glossário de requisitos** — a IA sugeriu criar um glossário específico para a especificação.
   Descartado porque o repositório já contém `docs/negocio/glossario.md`.

---

## Rastreabilidade (resumo)

| História | Requisitos Funcionais | Regras de Negócio | Caso de Uso |
|----------|----------------------|-------------------|-------------|
| HU-01 | RF-01 | RN-01 | UC-01 |
| HU-04, HU-05 | RF-06, RF-07, RF-08 | RN-07, RN-08, RN-03 | UC-02 |
| HU-06, HU-07, HU-08, HU-09 | RF-09–RF-15 | RN-09–RN-11 | UC-03 |
| HU-10, HU-11 | RF-05, RF-22, RF-23 | RN-04–RN-06 | UC-04 |
| HU-12, HU-13 | RF-16–RF-18 | RN-12, RN-13 | UC-05 |
| HU-14 | RF-19, RF-20 | — | — |

---

## Evolução — RAG Enterprise

A evolução do RAG do MVP para um RAG de nível corporativo foi especificada antes de qualquer
código, seguindo Spec-Driven Development. Os artefatos descrevem o comportamento esperado e servem
de base para os testes de cada fase.

### Situação da implementação

Atualizado em 2026-10-07.

| Fase | Especificação | Situação |
|------|---------------|----------|
| 1 — Avaliação e linha de base | SPEC-001 | Aprovada e implementada; em validação no ambiente Docker |
| 2 — Recuperação semântica | SPEC-002 | Rascunho; não iniciada |
| 3 — Busca híbrida, reranking e citações | SPEC-003 | Rascunho; não iniciada |
| 4 — Autenticação e controle de acesso | SPEC-004 | Rascunho; não iniciada |
| 5 — Ingestão e ciclo de vida | SPEC-005 | Rascunho; não iniciada |
| 6 — Operação e governança | SPEC-006 | Rascunho; não iniciada |

### Por que especificações SDD por fase?

A evolução tem seis fases com dependência entre si e decisões arquiteturais próprias. Uma
especificação por fase reúne, em um único lugar, o problema, os requisitos, os critérios de aceite
em Gherkin, o desenho da solução, o impacto arquitetural, a estratégia de testes e as decisões
ainda pendentes — e recebe um status de aprovação antes do início da implementação.
Os artefatos por tipo (RF, RNF, RN, HU, UC) continuam sendo a fonte única de cada requisito; as
especificações apenas os referenciam.

### Decisões que orientaram a especificação

- **Embeddings locais**, mantendo a ADR 0004: vetorização, busca esparsa, reranking e OCR rodam
  no próprio ambiente.
- **Keycloak** como único provedor de identidade.

### Rastreabilidade da evolução

| Fase | Especificação | Histórias | Requisitos Funcionais | Regras de Negócio | Casos de Uso | Casos de Teste |
|------|---------------|-----------|-----------------------|-------------------|--------------|----------------|
| 1 — Avaliação e linha de base | [SPEC-001](specs/SPEC-001-avaliacao-e-linha-de-base.md) | HU-15, HU-16 | RF-24–RF-27 | RN-14, RN-15 | UC-12 | CT-01–CT-05 |
| 2 — Recuperação semântica | [SPEC-002](specs/SPEC-002-recuperacao-semantica.md) | HU-17, HU-18 | RF-28–RF-32 | RN-16 | UC-11 | CT-06–CT-13 |
| 3 — Busca híbrida, reranking e citações | [SPEC-003](specs/SPEC-003-busca-hibrida-reranking-citacoes.md) | HU-19–HU-22 | RF-33–RF-39 | RN-17–RN-19 | UC-10 | CT-14–CT-22 |
| 4 — Autenticação e controle de acesso | [SPEC-004](specs/SPEC-004-autenticacao-e-controle-de-acesso.md) | HU-23–HU-27 | RF-40–RF-47 | RN-20–RN-25 | UC-06, UC-07, UC-13 | CT-23–CT-32 |
| 5 — Ingestão e ciclo de vida | [SPEC-005](specs/SPEC-005-ingestao-e-ciclo-de-vida.md) | HU-28–HU-32 | RF-48–RF-55 | RN-26–RN-30 | UC-08, UC-09 | CT-33–CT-40 |
| 6 — Operação e governança | [SPEC-006](specs/SPEC-006-operacao-e-governanca.md) | HU-33–HU-37 | RF-56–RF-63 | RN-31–RN-33 | UC-10 | CT-41–CT-48 |

### Itens do MVP revistos

| Item do MVP | Situação na evolução |
|-------------|----------------------|
| RF-07, UC-02 | Ingestão passa a ser assíncrona (RF-48, UC-08) |
| RF-10, UC-03 | Chat passa a usar busca híbrida, reranking e citações (RF-33 a RF-37, UC-10) |
| RNF-02 | Tempo de indexação medido em segundo plano; resposta do upload pelo RNF-17 |
| RN-08 | Substituída pela RN-26: arquivo idêntico não é duplicado |
| RN-11 | Refinada pela RN-19: histórico limitado por orçamento de tokens |
| Histórias de autenticação e permissões descartadas no MVP | Retomadas no Épico 10, agora dentro do escopo |

### Como a IA Generativa apoiou esta etapa

**Ferramenta utilizada:** Claude (Anthropic), em modo agente, com acesso de leitura ao código e à
documentação do repositório.

Os artefatos desta seção foram gerados pela IA a partir da leitura do código (ingestão,
adaptadores de embeddings e do Qdrant, fluxo de chat, rotas e modelos) e de duas decisões
informadas pelo autor: manter embeddings locais conforme a ADR 0004 e usar sempre o Keycloak.

**Situação da revisão:** em 2026-10-07 o autor aprovou a SPEC-001, com suas três decisões
(assistente piloto, tolerância de 0,02 e juiz de fidelidade), e validou como curador os 27 itens
do conjunto de referência piloto, com três ajustes nas fontes propostos pela IA. Os demais
artefatos continuam **pendentes de revisão do autor**, e ainda não há, como nas seções do MVP,
registro de sugestões aproveitadas, modificadas ou descartadas. Pontos que pedem validação humana
antes da aprovação de cada especificação restante:

- metas numéricas dos RNF-16 a RNF-21, que são valores iniciais a calibrar na Fase 1;
- as decisões listadas na seção "Decisões Pendentes" de cada especificação;
- a regra RN-24, sobre privacidade das conversas perante administradores;
- o limite de sequência do modelo de embedding apontado na SPEC-002, a confirmar na implementação.
