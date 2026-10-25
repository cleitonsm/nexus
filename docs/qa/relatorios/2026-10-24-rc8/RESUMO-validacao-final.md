# RESUMO da validação final — RAG Enterprise

Campanha oficial: **`validacao-final-rc8`** (commit `1bfc1fe`, 2026-10-24), etapas V0 a V8 no Docker
do autor, e **`validacao-final-rc9`** (commit `400ae33`), que repete a V2 (agora com a cobertura) e a
V4 e recebe a V5 depois da atualização do Angular 20 (PC-D12). O backend não mudou entre as duas.

**Situação: falta só a V5 manual (E1 a E11).** Tudo o que é automático passou: V0 a V8 na rc8 e,
na rc9, a V2 com a cobertura (95%) e a V4 sobre o Angular 20. Com a V5 aprovada, as SPEC-001 a 006
passam a `Implementada`.

Ambiente: Windows 11 com Docker Desktop (12 CPUs, i7-8750H, 7,7 GiB para o Docker), modelos locais
`paraphrase-multilingual-MiniLM-L12-v2` e `mmarco-mMiniLMv2-L12-H384-v1`, LLM `gemini-3.8-flash`
(PC-D8). Detalhes em [`00-ambiente.md`](00-ambiente.md) (o campo "Commit" saiu como desconhecido; o
commit é o `1bfc1fe`, que aparece no nome dos relatórios da avaliação e no CT-47/48).

## Etapas

| Etapa | Resultado | Evidência |
|---|---|---|
| V0 ambiente limpo e varreduras | OK | `V0-*.log` |
| V1 subida e migrações | OK | `V1-*.log` |
| V2 testes unitários no container (LangGraph real) | OK: 705 testes | `V2-testes-unitarios-no-container-.log` |
| V2 cobertura de domínio e aplicação (RNF-30) | rc9: **95%** (mínimo 80%), 705 testes; a rc8 não mediu (defeito do orquestrador, corrigido em `400ae33`) | [`../2026-10-24-rc9/02-cobertura.txt`](../2026-10-24-rc9/02-cobertura.txt) |
| V3 integração do backend | OK: 146 testes, nenhum pulado | `V3-testes-de-integracao-do-backend-.log` |
| V3 CT-53, CT-54, CT-56 | OK; CT-56 com 0 vazamentos | `V3-CT-5*.log`, [`ct56/leakage_scan.json`](ct56/leakage_scan.json) |
| V4 frontend (Angular 19) | OK: 149 testes, build; `npm audit`: 4 altas → PC-D12 | `V4-*.log` |
| V4 frontend (Angular 20) | rc9: OK, 149 testes, build de produção, `npm audit` com 0 vulnerabilidades | `../2026-10-24-rc9/V4-*.log` |
| V5 ponta a ponta (E1 a E11) | **Pendente**, manual com capturas (rc9) | — |
| V6 metas de qualidade (3 execuções) | OK | `V6-*.log`, linha de base abaixo |
| V7 desempenho (100.000 trechos) | OK; RNF-02 como limitação aceita | [`07-desempenho.md`](07-desempenho.md), CSVs em `07-desempenho/` |
| V8 CT-47, CT-48, portão de qualidade | OK | `V8-*.log`, [`../2026-10-24-ct47/resumo.md`](../2026-10-24-ct47/resumo.md), [`../2026-10-24-ct48/resumo.md`](../2026-10-24-ct48/resumo.md) |

## Metas de qualidade (V6, `nexus-docs-ampliado`, 82 itens validados pelo curador)

| Relatório | recall@5 | MRR | Fidelidade | Fallback fora do escopo | Geradas com citação |
|---|---|---|---|---|---|
| `20261024-194709-1bfc1fe` | 0,984 | 0,901 | 0,983 | 0,900 | 1,000 |
| `20261024-195725-1bfc1fe` | 0,984 | 0,909 | 1,000 | 0,900 | 1,000 |
| `20261024-200715-1bfc1fe` | 0,984 | 0,901 | 1,000 | 0,900 | 1,000 |
| **Meta** | ≥ 0,80 | — | média ≥ 0,90, nenhuma < 0,88 | ≥ 0,90 | 1,0 |

A taxa de resposta dentro do escopo (`citation_coverage`, 0,935) é informativa (decisão de 2026-10-21).
**Linha de base oficial**: estes três relatórios em `backend/tests/evaluation/reports/nexus-docs-ampliado/`
e o do portão de qualidade da V8 em `backend/tests/evaluation/reports/nexus-docs/20261024-225948-1bfc1fe.*`.

## Desempenho (V7)

| Cenário | Amostras | p50 | p95 | Máx. | Erros | Critério | Veredito |
|---|---:|---:|---:|---:|---:|---|---|
| RNF-01 primeiro texto do chat (Gemini real) | 100 | 4,52 s | 7,42 s | 10,08 s | 0 | p95 ≤ 30 s | Aprovado |
| RNF-17 upload de 25 MB | 20 | 0,24 s | 1,05 s | 1,36 s | 0 | todas ≤ 2 s | Aprovado |
| RNF-02 indexação de 10 MB | 20 | 91,6 s | 126,0 s | 126,3 s | 0 | todas ≤ 60 s | Limitação aceita (PC-D11) |
| RNF-03 busca densa | 200 | 0,010 s | 0,013 s | 0,039 s | 0 | todas ≤ 2 s | Aprovado |
| RNF-16 busca híbrida, 1 usuário | 200 | 0,82 s | 0,98 s | 3,52 s | 0 | p95 ≤ 3 s | Aprovado |
| RNF-16 busca híbrida, 5 usuários | 200 | 3,86 s | 4,25 s | 6,05 s | 0 | — | Informativo |
| RNF-18 busca durante a reindexação | 2.100 | 1,62 s | 2,07 s | 5,95 s | 0 | — | Informativo (0 erros) |

## Defeitos encontrados e corrigidos nos ensaios (2026-10-21 a 24)

| Defeito | Correção |
|---|---|
| Perguntas simultâneas no chat: `RuntimeError: Already borrowed` (502) no tokenizador dos modelos locais | Uma trava por modelo (`028362d`, `0445b4e`) |
| Primeiras perguntas simultâneas após o backend subir corrompiam o torch (`Cannot copy out of meta tensor`) até reiniciar | Carregamento dos modelos um por vez no processo (`34efcbf`) |
| Angular ≤ 19.2.25 com 4 vulnerabilidades altas, sem correção na linha 19 | Angular 20.3.34 e NgRx 20.1 (PC-D12, `2e60c12`) |
| A V2 não media a cobertura exigida pelo RNF-30 | Cobertura na V2 (`400ae33`) |

Os demais ajustes dos ensaios foram nas ferramentas de medição (`scripts/perf/`, `run-all.sh`).

## Limitações aceitas (PC-D7)

- Tabelas em PDF extraídas como texto corrido (D11).
- Limite de uso não atômico: duas perguntas simultâneas podem passar juntas no limite (C2).
- `/metrics` exposto na porta 8000 só no ambiente local (C9).
- Backup só local (D5).
- Sem tela de versões substituídas de documentos (D5 da SPEC-005).
- **RNF-02 nesta máquina (PC-D11)**: um documento de 10 MB com ~300 páginas de texto leva 92 a 126 s;
  o vetor denso sozinho faz ~33 trechos/s em CPU. Otimização no ciclo 2 (fragmentação sem recontagem,
  modelo otimizado ou GPU).

Ressalva: **RNF-11** — o domínio não importa framework, mas a aplicação usa o LangGraph diretamente em
`chat_with_assistant.py` e `infer_assistant.py`, enquanto a ADR 0002 o põe na infraestrutura. Registrado
como risco do ciclo 2.

## Metas do escopo e critérios de aceite

| Meta ([escopo](../../../negocio/escopo-rag-enterprise.md)) | Medido | Evidência | Resultado |
|---|---|---|---|
| Recall@5 ≥ 0,80 | 0,984 nas 3 execuções | V6 | Aprovado |
| Fidelidade ≥ 0,90 | média 0,994 (mínimo 0,983) | V6 | Aprovado |
| Fallback fora do escopo ≥ 90% | 0,90 nas 3 execuções | V6 | Aprovado |
| 100% das respostas geradas com fonte | 1,0 nas 3 execuções | V6 | Aprovado |
| Zero vazamento | 0 trechos de documento não autorizado | CT-56 (`ct56/leakage_scan.json`), CT-28 | Aprovado |
| Upload ≤ 2 s | máximo 1,36 s (25 MB) | V7, CT-40 | Aprovado |
| 100% rastreáveis | identificador da requisição em todas as linhas de log e um span por etapa | CT-05, CT-44 (V3) | Aprovado |

| Critério de aceite da evolução | Evidência | Resultado |
|---|---|---|
| Usuário só recebe respostas de documentos que seus grupos acessam | CT-27, CT-28, CT-56 (V3); E5 na V5 | Aprovado nos testes automáticos; E5 pendente |
| Toda resposta gerada apresenta as fontes | CT-15, CT-20 (V2, V3); 100% na V6; E4 na V5 | Aprovado nos testes automáticos; E4 pendente |
| Fora do escopo resulta em fallback explícito, sem chamar o LLM | CT-14 (V2); fallback 0,90 na V6 | Aprovado |
| Excluir ou substituir um documento altera as respostas sem remover o assistente | CT-36, CT-38, CT-50 (V2, V3); E3 e E4 na V5 | Aprovado nos testes automáticos; E3/E4 pendentes |
| Metas verificadas por um comando repetível | `scripts/eval.sh` (V6, 3 execuções); portão de qualidade e CT-48 (V8) | Aprovado |
| Ambiente completo sobe com um único comando | V1 (`docker compose up -d --build --wait`, com Keycloak e worker) | Aprovado |

## Matriz requisito → caso → evidência → resultado

Contagem (86 requisitos): 67 aprovados, 13 aprovados nos testes automáticos com o cenário da V5
pendente, 4 pendentes da V5 (RNF-13, 14, 15 e 33, só verificáveis na tela), 1 limitação aceita
(RNF-02) e 1 aprovado com ressalva (RNF-11). Etapas citadas: pasta da rc8, salvo indicação.

## Requisitos funcionais (RF-24 a RF-74)

| Requisito | Descrição | Casos | Evidência | Resultado |
|---|---|---|---|---|
| RF-24 | O sistema deve manter, por assistente, um conjunto de referência versionado no repositório, em… | CT-02 | V2 (705 unitários OK) | Aprovado |
| RF-25 | O sistema deve oferecer um comando de avaliação que executa o pipeline de RAG contra o… | CT-01, CT-04 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado); V6 (3 execuções, Gemini) | Aprovado |
| RF-26 | O sistema deve gravar um relatório de cada avaliação, identificando commit, modelos e… | CT-03, CT-04 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-27 | O sistema deve emitir logs estruturados em JSON com um identificador de requisição propagado… | CT-05 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-28 | O sistema deve gerar embeddings com um modelo semântico multilíngue executado localmente,… | CT-10, CT-11 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-29 | O sistema deve fragmentar os documentos respeitando sua estrutura (títulos, parágrafos, listas… | CT-06, CT-07 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-30 | O sistema deve gravar em cada chunk, além dos metadados mínimos do MVP, o título da seção, a… | CT-08 | V2 (705 unitários OK) | Aprovado |
| RF-31 | O sistema deve permitir reindexar a base de um assistente sem indisponibilidade, construindo… | CT-09, CT-12 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado); RNF-18 na V7 (`07-desempenho.md`) | Aprovado |
| RF-32 | O sistema deve registrar, por documento, o modelo de embedding e a versão do pipeline de… | CT-08 | V2 (705 unitários OK) | Aprovado |
| RF-33 | O sistema deve recuperar candidatos por busca híbrida, combinando vetor denso e vetor esparso… | CT-18 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-34 | O sistema deve reordenar os candidatos recuperados com um modelo de reranking executado… | CT-19 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-35 | O sistema deve descartar candidatos abaixo de uma nota mínima de relevância configurável e… | CT-14 | V2 (705 unitários OK); fallback 0,90 na V6 (3 execuções, Gemini) | Aprovado |
| RF-36 | O sistema deve reescrever a pergunta do usuário em uma consulta autônoma, usando o histórico… | CT-17 | V2 (705 unitários OK) | Aprovado |
| RF-37 | O sistema deve devolver, junto com cada resposta gerada, as citações dos trechos utilizados… | CT-15, CT-20, CT-50 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado); geradas com citação 1,0 na V6 (3 execuções, Gemini) | Aprovado |
| RF-38 | O sistema deve exibir no chat as fontes de cada resposta, permitindo consultar o trecho citado. | CT-21, E4 | V4 rc9 (Angular 20: 149 testes, build, 0 vulnerabilidades); V5 — pendente (manual) | Aprovado (V4); E4 pendente |
| RF-39 | O sistema deve limitar o histórico e o contexto enviados ao LLM a um orçamento de tokens… | CT-16 | V2 (705 unitários OK) | Aprovado |
| RF-40 | O sistema deve autenticar usuários exclusivamente pelo Keycloak, via OpenID Connect… | CT-26, CT-52 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-41 | O sistema deve reconhecer os papéis administrador, curador e usuário a partir do token emitido… | CT-30, CT-52 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-42 | O sistema deve permitir vincular assistentes a grupos do Keycloak e exibir a cada usuário… | CT-27, E5 | V3 (146 de integração OK, nenhum pulado); V5 — pendente (manual) | Aprovado (V3); E5 pendente |
| RF-43 | O sistema deve permitir restringir um documento a grupos específicos e aplicar essa restrição… | CT-28, CT-56, E5 | V3 (146 de integração OK, nenhum pulado); CT-56 sem vazamento; V5 — pendente (manual) | Aprovado (V3); E5 pendente |
| RF-44 | O sistema deve associar cada conversa ao usuário que a criou e permitir o acesso ao seu… | CT-29 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-45 | O sistema deve registrar trilha de auditoria de autenticações, perguntas realizadas,… | CT-31, E6 | V3 (146 de integração OK, nenhum pulado); V5 — pendente (manual) | Aprovado (V3); E6 pendente |
| RF-46 | O frontend deve oferecer login, logout e renovação de sessão pelo Keycloak e ocultar… | CT-32, E1 | V4 rc9 (Angular 20: 149 testes, build, 0 vulnerabilidades); V5 — pendente (manual) | Aprovado (V4); E1 pendente |
| RF-47 | O sistema deve restringir ao papel administrador a configuração e o teste da chave de API do… | CT-30 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-48 | O sistema deve processar a ingestão de forma assíncrona: o upload registra o documento,… | CT-33, CT-50 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-49 | O sistema deve expor e exibir o estado de cada documento (pendente, processando, indexado,… | CT-33, CT-50 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-50 | O sistema deve permitir excluir um documento, removendo seus vetores e o arquivo original. | CT-38, CT-50 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-51 | O sistema deve permitir substituir um documento por uma nova versão, mantendo a versão… | CT-36, E3 | V2 (705 unitários OK); V5 — pendente (manual) | Aprovado (V2); E3 pendente |
| RF-52 | O sistema deve detectar o envio de arquivo idêntico a um documento já existente no mesmo… | CT-34, E3 | V2 (705 unitários OK); V5 — pendente (manual) | Aprovado (V2); E3 pendente |
| RF-53 | O sistema deve extrair texto de PDFs digitalizados por OCR executado localmente e preservar o… | CT-39, CT-54 | V3 (146 de integração OK, nenhum pulado); CT-54 (OCR sem internet) | Aprovado |
| RF-54 | O sistema deve armazenar o arquivo original de cada documento e permitir reprocessá-lo sem… | CT-33, E3 | V2 (705 unitários OK); V5 — pendente (manual) | Aprovado (V2); E3 pendente |
| RF-55 | O sistema deve repetir automaticamente o processamento de um documento em caso de falha… | CT-35 | V2 (705 unitários OK) | Aprovado |
| RF-56 | O sistema deve registrar rastreamento distribuído de cada resposta, com um trecho (span) por… | CT-44 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-57 | O sistema deve expor métricas de latência por etapa, consumo de tokens e custo estimado por… | CT-44, E8 | V3 (146 de integração OK, nenhum pulado); V5 — pendente (manual) | Aprovado (V3); E8 pendente |
| RF-58 | O sistema deve transmitir a resposta do chat em streaming à medida que o LLM a gera. | CT-45, CT-55, E7 | V3 (146 de integração OK, nenhum pulado); RNF-01 na V7 (`07-desempenho.md`); V5 — pendente (manual) | Aprovado (V3, V7); E7 pendente |
| RF-59 | O sistema deve aplicar limite de uso por usuário e tamanho máximo de upload, ambos… | CT-41, CT-55, E7 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado); V5 — pendente (manual) | Aprovado (V2, V3); E7 pendente |
| RF-60 | O sistema deve tratar o conteúdo recuperado dos documentos como dado delimitado no prompt,… | CT-42, E11 | V2 (705 unitários OK); V5 — pendente (manual) | Aprovado (V2); E11 pendente |
| RF-61 | O sistema deve permitir ao usuário avaliar cada resposta como útil ou não útil, com comentário… | CT-43, E7 | V2 (705 unitários OK); V5 — pendente (manual) | Aprovado (V2); E7 pendente |
| RF-62 | O sistema deve executar a avaliação de qualidade na integração contínua e bloquear mudanças… | CT-03, CT-48 | V2 (705 unitários OK); V8 (CT-48: a avaliação falhou com código 1) | Aprovado |
| RF-63 | O sistema deve oferecer rotina de backup do PostgreSQL e de snapshot do Qdrant, com… | CT-47 | V8 (backup, ambiente limpo, restauração, consistência e busca) | Aprovado |
| RF-64 | apenas mensagens user podem ser adicionadas diretamente a uma | CT-58 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-65 | uploads maiores que UPLOAD_MAX_BYTES respondem 413 sem carregar o arquivo inteiro; a leitura… | CT-59, CT-55 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-66 | a reserva dos jobs de ingestão e de reindexação é renovada durante o trabalho; escrita de quem… | CT-60 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-67 | fora do ambiente local, segredos padrão impedem a partida; a mensagem cita o nome da variável,… | CT-61 | V2 (705 unitários OK) | Aprovado |
| RF-68 | o administrador consulta a configuração efetiva do LLM (provedor, modelo, URL, se a chave está… | CT-64, CT-68 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-69 | o administrador altera provedor, modelo e URL; a mudança vale a partir da próxima pergunta e… | CT-63, CT-66, CT-67, CT-68 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-70 | chat (incluindo streaming), teste da chave, registro de consumo e comando de avaliação usam a… | CT-64, CT-70 | V2 (705 unitários OK); V6 (3 execuções, Gemini) e RNF-01 da V7 com o Gemini configurado na tela | Aprovado |
| RF-71 | a alteração gera evento de auditoria com o valor anterior e o novo (provedor, modelo e URL),… | CT-65, CT-66, CT-68 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RF-72 | a tela de administração mostra os campos, a origem do valor, o aviso de chave por provedor… | CT-69 | V4 rc9 (Angular 20: 149 testes, build, 0 vulnerabilidades) | Aprovado |
| RF-73 | chamadas ao LLM (teste da chave, pergunta com e sem streaming, avaliação) repetem a | CT-71 a CT-73 | V2 (705 unitários OK) | Aprovado |
| RF-74 | envio de documento e alteração dos grupos de um documento recusam grupos que não existem | CT-74 a CT-76 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado); CT-56 com `view-users` | Aprovado |

## Requisitos não funcionais (RNF-01 a RNF-33)

| Requisito | Descrição | Casos | Evidência | Resultado |
|---|---|---|---|---|
| RNF-01 | O sistema deve retornar os primeiros tokens da resposta do chat em até 30 segundos para 95%… | ttft.py (100 perguntas, LLM real) | V7 (`07-desempenho.md`): p95 7,4 s, 0 erros | Aprovado |
| RNF-02 | A indexação de um documento de até 10 MB deve ser concluída em até 60 segundos. | indexing_time.py (20 documentos de 10 MB) | V7 (`07-desempenho.md`): 92–126 s | Limitação aceita (PC-D11) |
| RNF-03 | A busca vetorial deve retornar os top-k chunks em menos de 2 segundos para bases com até… | retrieval_latency.py dense (100.000 trechos) | V7 (`07-desempenho.md`): máximo 0,039 s | Aprovado |
| RNF-04 | A chave de API do provedor LLM deve ser armazenada criptografada no banco de dados usando… | testes da chave do LLM | V2 (705 unitários OK) (`test_use_cases`); V3 (146 de integração OK, nenhum pulado) (`test_api_routes`) | Aprovado |
| RNF-05 | A chave de criptografia não deve ser armazenada no banco de dados; deve ser fornecida via… | CT-61 | V2 (705 unitários OK) (segredo só no ambiente; ausente ou padrão impede a partida) | Aprovado |
| RNF-06 | O sistema não deve expor a chave de API do LLM em nenhuma resposta de API pública. | CT-66, CT-68, CT-46 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado); CI | Aprovado |
| RNF-07 | Cada assistente deve possuir uma collection independente no Qdrant; uma consulta de um… | CT-51 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RNF-08 | A exclusão de um assistente deve remover a collection associada no Qdrant, garantindo que… | CT-51 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RNF-09 | O ambiente completo (backend, frontend, banco de dados, vetor store) deve subir localmente com… | V1 | V1 da rc8 (`up --build --wait`, um comando) | Aprovado |
| RNF-10 | O sistema deve ser compatível com provedores LLM que implementam a interface OpenAI Chat… | V6, CT-70 | Gemini pelo endpoint compatível com OpenAI na V6 (3 execuções, Gemini) e na V7 | Aprovado |
| RNF-11 | O backend deve seguir Clean Architecture, separando domínio, aplicação, infraestrutura e API,… | revisão | Domínio sem import de framework (varredura de 2026-10-24); a aplicação importa o LangGraph no chat e na inferência, divergindo da ADR 0002 (registrado para o ciclo 2) | Aprovado com ressalva |
| RNF-12 | O frontend deve seguir o padrão NgRx com estado centralizado, garantindo que toda mutação de… | CT-21, CT-69, FE-02, FE-05 | V4 rc9 (Angular 20: 149 testes, build, 0 vulnerabilidades) | Aprovado |
| RNF-13 | O sistema deve fornecer feedback visual (indicador de carregamento) para todas as operações… | E10 | V5 — pendente (manual) | Pendente (V5) |
| RNF-14 | O sistema deve exibir mensagens de erro compreensíveis ao usuário para falhas de comunicação… | E9 | V5 — pendente (manual) | Pendente (V5) |
| RNF-15 | A interface deve ser responsiva, funcionando adequadamente em telas com largura mínima de 360… | E10 | V5 — pendente (manual) | Pendente (V5) |
| RNF-16 | A recuperação (busca híbrida e reranking) deve ser concluída em até 3 segundos para 95% das… | retrieval_latency.py hybrid (100.000 trechos) | V7 (`07-desempenho.md`): p95 0,98 s com 1 usuário; 5 usuários p95 4,2 s (informativo) | Aprovado |
| RNF-17 | O upload de um documento de até 25 MB deve responder em até 2 segundos, devolvendo o… | CT-40, upload_latency.py | V3 (146 de integração OK, nenhum pulado); V7 (`07-desempenho.md`): máximo 1,36 s, com o worker pausado (decisão de 2026-10-22) | Aprovado |
| RNF-18 | A reindexação de um assistente não deve interromper nem degradar as consultas à base vigente. | CT-12, reindex_under_load.py | V3 (146 de integração OK, nenhum pulado); V7 (`07-desempenho.md`): 2.100 buscas durante a reindexação, 0 erros, p95 2,1 s | Aprovado |
| RNF-19 | O recall@5 da recuperação deve ser de no mínimo 0,80 no conjunto de referência de cada… | CT-13 | V6 (3 execuções, Gemini): recall@5 0,984 nas 3 | Aprovado |
| RNF-20 | A fidelidade das respostas ao contexto recuperado deve ser de no mínimo 0,90 no conjunto de… | CT-22 | V6 (3 execuções, Gemini): fidelidade 0,983 / 1,0 / 1,0 (média 0,994) | Aprovado |
| RNF-21 | Pelo menos 90% das perguntas fora do escopo da base devem resultar em fallback explícito. | CT-22 | V6 (3 execuções, Gemini): fallback 0,90 nas 3 | Aprovado |
| RNF-22 | Todo token de acesso deve ser validado no backend quanto a assinatura (JWKS do Keycloak),… | CT-23, CT-52 | V2 (705 unitários OK); V3 (146 de integração OK, nenhum pulado) (Keycloak real) | Aprovado |
| RNF-23 | As restrições de acesso devem ser aplicadas no servidor, dentro da consulta ao vector store; o… | CT-28, CT-56 | V3 (146 de integração OK, nenhum pulado); CT-56: 0 vazamentos, todos os controles recuperaram o permitido | Aprovado |
| RNF-24 | A trilha de auditoria deve ser somente de inclusão (append-only), com retenção configurável e… | CT-31, purga de retenção (D6) | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RNF-25 | Logs, rastreamentos e métricas não devem conter segredos, tokens de acesso nem o conteúdo… | CT-46 | V3 (146 de integração OK, nenhum pulado); CI | Aprovado |
| RNF-26 | Embeddings densos, vetores esparsos, reranking e OCR devem ser executados localmente; nessas… | CT-10, CT-54 | V3 (146 de integração OK, nenhum pulado); CT-54 sem internet | Aprovado |
| RNF-27 | O processamento de ingestão deve ser idempotente e retomável: a falha ou reinício do worker… | CT-37, CT-53 | V3 (146 de integração OK, nenhum pulado); CT-53 (kill e stop do worker) | Aprovado |
| RNF-28 | O ponto de recuperação (RPO) dos dados relacionais e vetoriais deve ser de no máximo 24 horas. | CT-47 | V8 | Aprovado |
| RNF-29 | Toda requisição de chat deve ser rastreável de ponta a ponta por um único identificador, da… | CT-44 | V3 (146 de integração OK, nenhum pulado) | Aprovado |
| RNF-30 | Todo componente novo deve ser introduzido atrás de uma porta do domínio, com cobertura de… | cobertura de domínio e aplicação | V2 da rc9: 95% (`../2026-10-24-rc9/02-cobertura.txt`); a rc8 não mediu | Aprovado |
| RNF-31 | Toda alteração de esquema do banco deve ser feita por migração versionada e reversível. | CT-49 | V3 (146 de integração OK, nenhum pulado) (`test_migrations`); V1 (revisão das migrações) | Aprovado |
| RNF-32 | O ambiente completo, incluindo Keycloak e worker de ingestão, deve continuar subindo com um… | V1 | V1 da rc8 (Keycloak e worker no mesmo comando; modelos no volume de cache) | Aprovado |
| RNF-33 | As fontes de uma resposta devem estar acessíveis em um clique, e o estado de ingestão deve ser… | E2, E4 | V5 — pendente (manual) | Pendente (V5) |
