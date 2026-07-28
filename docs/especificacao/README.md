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
