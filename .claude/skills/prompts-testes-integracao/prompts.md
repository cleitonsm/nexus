# Prompts de teste de integração do Nexus

Cada seção traz o prompt (copiar e preencher os `{{campos}}`), um trecho da saída que ele produziu e o teste em que ela virou código. A última seção registra os ajustes que melhoraram as respostas.

---

## 1. Cenários de integração (caminho feliz e fluxo entre módulos)

**Objetivo:** cobrir o fluxo completo de um endpoint entre os componentes.

```text
Você é um engenheiro de QA de uma plataforma RAG corporativa (FastAPI, PostgreSQL,
Qdrant, Keycloak). Analise o endpoint {{METODO}} {{ROTA}}.

Contexto:
- O endpoint {{DESCRICAO}}.
- A busca no Qdrant filtra por user_groups e active; a resposta traz citações
  (document_id, chunk_id, source_name, section_path, page, score, excerpt,
  document_available).
- Parâmetros relevantes: {{PARAMETROS}} (ex.: question, top_k, stream).

Liste de 5 a 8 cenários de integração, do documento indexado até a resposta
persistida na conversa. Para cada cenário informe:
ID | Pré-condição | Passos | Resultado esperado (status HTTP e campos do corpo) | Componentes envolvidos

Restrições:
- Não simule a API nem o banco; apenas o LLM pode ser simulado, com resposta fixa.
- Inclua ao menos um cenário de borda (pergunta fora do escopo, documento removido,
  limite de parâmetro).
- Use apenas dados fictícios.
```

**Saída obtida (resumo):**

| ID | Cenário | Resultado esperado |
|---|---|---|
| C1 | Pergunta com trecho relevante (score 0,9) | 201, `fallback_used=false`, 1 citação gravada na mensagem do assistente e nenhuma na do usuário |
| C2 | Documento citado foi excluído depois | 200 em `GET /conversations/{id}`, citação mantida com `document_available=false` |
| C3 | Pergunta fora do escopo (score 0,2) | 201, `fallback_used=true`, `citations=[]`, `used_context_chunks=0` |
| C4 | `top_k=2` com 6 trechos disponíveis | só 2 trechos usados no contexto |
| C5 | `stream=true` | texto em partes, citações no evento final |
| C6 | Erro antes do primeiro byte no streaming | status HTTP de erro preservado |
| C7 | Índice incompatível com o modelo de embedding | 409 (conflito) |

**Virou:** `backend/tests/integration/test_chat_citations.py`.

---

## 2. Casos de erro e segurança (testes negativos)

**Objetivo:** encontrar falhas de autenticação, autorização e vazamento de informação.

```text
Atue como pentester e engenheiro de QA. A API {{NOME_API}} usa Bearer JWT emitido
pelo Keycloak (realm {{REALM}}), papéis {{PAPEIS}} e grupos que limitam quais
assistentes cada usuário vê. Rotas protegidas: {{LISTA_DE_ROTAS}}. Só /health é
pública.

Liste casos de teste negativos de integração nestas categorias:
1. Autenticação: token ausente, malformado, de outro emissor, de outra audiência,
   expirado, assinado por outra chave, outro esquema (Basic, sem prefixo, "Bearer" vazio).
2. Autorização por grupo: usuário de outro grupo listando, conversando ou
   reindexando um assistente.
3. Autorização por papel: não administrador em rotas de administração.
4. Propriedade: conversa de outro usuário, conversa inexistente, tentativa de
   forjar mensagem com role assistant/system.

Para cada caso: ID | Requisição | Status esperado (401, 403 ou 404) | Corpo esperado
| Efeito colateral que NÃO pode ocorrer | Por que esse status.

Atenção: quando a diferença entre 403 e 404 revelar que um recurso existe, prefira
404 e explique.
```

**Saída obtida (resumo):**

| ID | Caso | Esperado |
|---|---|---|
| E1 | Qualquer rota sem token (exceto `/health`) | 401, `{"code": "unauthenticated"}`, cabeçalho `WWW-Authenticate: Bearer` |
| E2 | Token malformado, de outro emissor, de outra audiência, expirado ou de outra chave | 401, `"invalid or expired token"` |
| E3 | `Basic <token>`, token sem prefixo, `Bearer` vazio | 401 |
| E4 | Usuário do grupo errado abre conversa no assistente de RH | 403, nenhuma conversa criada, evento `access.denied` auditado |
| E5 | Mesmo usuário pergunta no chat | 403, **nenhuma busca no Qdrant**, nenhuma mensagem gravada, resposta sem trecho do documento |
| E6 | Não administrador nas rotas de chave do LLM | 403 |
| E7 | Conversa de outro usuário ou inexistente | 404 nos dois casos (indistinguíveis) |
| E8 | Dono tenta gravar mensagem com role `assistant`/`system` | rejeitado |

**Virou:** `backend/tests/integration/test_access_control_api.py` (matriz rota × token com `subTest`).

---

## 3. Dados de teste e isolamento

**Objetivo:** gerar dados determinísticos que provem que um assistente não enxerga a base do outro.

```text
Preciso de dados de teste fictícios para provar o isolamento entre dois
assistentes de uma plataforma RAG: cada um tem sua própria collection no Qdrant
e a busca é semântica.

Gere:
1. Dois documentos Markdown curtos (título + 1 parágrafo, até 25 palavras) sobre
   assuntos corporativos que NÃO compartilham vocabulário nem tema, para evitar
   falso positivo na busca por similaridade.
2. Para cada documento, uma pergunta que só ele responde.
3. As asserções do teste: quais source_name NÃO podem aparecer nas citações de
   cada resposta e o que deve acontecer no Qdrant (alias e collection) ao excluir
   o primeiro assistente.

Sem dados pessoais, nomes de empresas reais ou números de documentos.
```

**Saída obtida:**

```python
DOCS = {
    "ferias.md": "# Ferias\n\nO colaborador tem trinta dias corridos de ferias por ano.\n",
    "estacionamento.md": "# Estacionamento\n\nO estacionamento da matriz abre as sete horas e fecha as vinte horas.\n",
}
# Assistente A (ferias.md)        <- "Que horas abre o estacionamento?" -> estacionamento.md fora das citações
# Assistente B (estacionamento.md) <- "Quantos dias de ferias?"          -> ferias.md fora das citações
# DELETE /assistants/{A}: 204; alias assistant-{A} some; collection assistant-{A}-v2 responde 404;
# alias assistant-{B} continua.
```

**Virou:** `backend/tests/integration/test_assistant_isolation.py` (CT-51, pilha real com `FakeLLMServer`).

---

## Ajustes de prompt que fizeram diferença

| Versão inicial | Problema | Ajuste |
|---|---|---|
| "Gere testes de integração para a API de chat." | Casos genéricos ("verificar se responde 200") | Dar endpoint, filtros, campos da resposta e stack |
| Sem formato de saída | Texto corrido, difícil de virar código | Exigir tabela ID / pré-condição / passos / resultado |
| Sem restrição de mocks | A LLM simulava banco e Qdrant, virando teste unitário | "Só o LLM pode ser simulado" |
| Dados sem restrição | Documentos com tema próximo causavam falso positivo na busca | "Assuntos que não compartilham vocabulário" |
| Status sem justificativa | A LLM sugeria 403 para conversa alheia | Pedir o "porquê" e orientar 404 quando 403 revela existência |
| Só caminho feliz | Nenhum efeito colateral verificado | Pedir "efeito que NÃO pode ocorrer" (busca, gravação, auditoria) |

Toda saída foi conferida contra a SPEC antes de virar teste: a LLM é copiloto, a especificação é a fonte da verdade.
