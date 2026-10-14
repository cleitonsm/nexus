# Troubleshooting

## Porta em Uso

Verifique se outro processo já usa as portas `4200`, `8000`, `5432` ou `6333`.

## Containers sem Comunicação

Confirme se os serviços usam nomes internos do Docker Compose, como `postgres` e `qdrant`, em
vez de `localhost` dentro dos containers.

## Embeddings Lentos

Modelos locais podem exigir mais CPU e memória. Para o MVP, prefira um modelo pequeno antes de
otimizar qualidade.

## Respostas sem Contexto

Verifique se o documento foi indexado na collection correta e se a pergunta está sendo executada
com o `assistant_id` esperado.

## Avaliação de Qualidade e Logs (Fase 1)

### Avaliação Encerra com Código 2

O conjunto de referência tem item inválido. Os problemas aparecem nos logs como
`evaluation.dataset.invalid`; as causas comuns são item sem `validated_by`, sem
`source_documents` ou com `id` repetido.

### Avaliação Encerra com Código 1

Alguma métrica caiu além de `EVAL_REGRESSION_TOLERANCE` em relação ao relatório anterior. O resumo
`.md` gerado ao lado do relatório indica qual.

### Fidelidade e Fallback Aparecem como "n/d"

Não há chave de LLM configurada ou o comando foi executado com `--no-generation`; nesse caso só a
recuperação é medida.

### A Avaliação Não Reflete Documentos Alterados

Os documentos do piloto só são indexados quando o assistente "Nexus Docs (avaliacao)" está vazio.
Exclua o assistente pela interface e execute a avaliação novamente.

### Logs em JSON Difíceis de Ler

Os logs do backend são uma linha JSON por evento. Filtre pelo campo `request_id` ou `event`.

## Evolução RAG Enterprise (Problemas Previstos)

Situações esperadas com as Fases 4 a 6 (código entregue; validação no Docker pendente).

### Login em Laço ou Erro 401

Verifique se o emissor e a audiência do token coincidem com `KEYCLOAK_URL`, `KEYCLOAK_REALM` e
`OIDC_AUDIENCE`. O endereço do Keycloak visto pelo navegador e o visto pelo backend dentro da rede
do Compose precisam resultar no mesmo emissor.

Na Fase 4, o frontend não entra em laço: quando a API recusa o token recém-emitido, ele mostra
a tela "Não foi possível entrar no Nexus". O motivo exato fica no log do backend, no evento
`auth.token.rejected` (`unexpected token issuer`, `unexpected token audience`,
`identity provider keys are unavailable`, `token without subject`...). O emissor esperado é
`KEYCLOAK_URL/realms/KEYCLOAK_REALM`; as chaves são buscadas em `KEYCLOAK_INTERNAL_URL`.

### Assistentes ou Conversas "Sumiram" após Ativar a Autenticação

Assistentes sem grupo vinculado são visíveis apenas a administradores, e conversas anteriores à
autenticação não têm dono. Vincule grupos aos assistentes pela tela de permissões.

### Documento Parado em "Pendente"

Confirme se o serviço `worker` está em execução e consulte seus logs. Jobs reservados e não
concluídos voltam à fila após o tempo limite.

### Primeira Ingestão Muito Lenta

O modelo de embedding é baixado no primeiro uso. Confirme se o volume `backend_cache` está montado
para que o download não se repita.

### Busca sem Resultados após Trocar o Modelo de Embedding

Vetores de modelos diferentes não são comparáveis. Execute a reindexação do assistente.

### Respostas Sempre em Fallback

Leia o log do chat antes de mexer em qualquer valor:

```powershell
docker compose logs backend --since 10m | Select-String "chat\.(retrieval|rerank|context|answer|fallback)"
```

| No log | Causa | O que fazer |
|--------|-------|-------------|
| `chat.retrieval.finished` com `candidates: 0` | Nenhum trecho passa nos filtros da busca: o documento não está indexado, está inativo, ou o usuário não tem nenhum dos grupos de `allowed_groups` | Conferir o estado do documento e os grupos (veja abaixo) |
| Candidatos maiores que 0 e `top_score` abaixo de `RELEVANCE_MIN_SCORE`, com `context_chunks: 0` | A nota mínima de relevância pode estar alta demais | Ajustar `RELEVANCE_MIN_SCORE` com base na avaliação, nunca por tentativa isolada (CT-22) |
| `context_chunks` maior que 0 e depois `chat.answer.rejected` (`no_valid_citation`) | O modelo respondeu sem o marcador `[n]` de nenhum trecho enviado (RN-18) | Revisar a instrução de citação, com decisão do autor |

Para ver o que há no Qdrant (a chave é `QDRANT_API_KEY`, padrão `nexus-local`; no PowerShell
passe o corpo por `|` e `--data-binary "@-"` em vez de aspas dentro do `-d`):

```powershell
$k = "nexus-local"; $c = "assistant-<id>-v2"; $u = "http://localhost:6333/collections/$c/points"
'{"limit":1,"with_payload":["allowed_groups","active","document_id"],"with_vector":false}' | curl.exe -s -H "api-key: $k" -H "Content-Type: application/json" -X POST "$u/scroll" --data-binary "@-"
```

Um `allowed_groups` com texto como `["Sem restrição"]` é um **grupo** com esse nome, e ninguém o tem:
o documento fica invisível. Documento sem restrição tem a lista vazia. Limpe os grupos do documento
na tela de assistentes (não edite o Qdrant à mão: o banco ficaria divergente). Desde a SPEC-009,
o envio recusa grupos que não existem no Keycloak.

### `/api/groups` Responde 503

A lista de grupos vem do cliente de serviço `nexus-backend` do Keycloak (PC-D6). O 503 significa que
o backend não conseguiu o token desse cliente ou ler os grupos. A causa usual é um realm importado
antes de 2026-10-08, que não tem o cliente, porque a importação não sobrescreve um realm existente.
Confirme com `docker compose logs backend --since 15m | Select-String "group directory"`. Para
recriar o realm (apaga só o banco `keycloak`: usuários e grupos criados à mão se perdem):

```powershell
docker compose stop keycloak
docker compose exec postgres psql -U nexus -d postgres -c "DROP DATABASE keycloak;"
docker compose exec postgres psql -U nexus -d postgres -c "CREATE DATABASE keycloak;"
docker compose up -d keycloak
```

Enquanto o 503 durar, a tela volta ao campo de texto livre e a validação de grupos do envio é
ignorada (e registrada em log).

### Teste do LLM Responde 502 ou 503 do Provedor

`401` do provedor: a chave não é do provedor escolhido na tela de administração (provedor, modelo
e URL são configuráveis desde a SPEC-008; a chave é a mesma para todos). `503` com "high demand"
(Gemini) ou `429`: falha passageira do provedor; o cliente já repete até três vezes (SPEC-009) e o
erro só chega à tela depois da última tentativa. Tente de novo ou troque o modelo.

### Respostas sem Trecho de um Documento Indexado (PostgreSQL e Qdrant Divergentes)

Uma falha no meio de uma gravação pode deixar o banco e o Qdrant com contagens diferentes (risco
R18). Confira com o comando sob demanda (decisão PC-D3):

```bash
docker compose run --rm --no-deps backend python -m src.cli.check_consistency
# ou um assistente só:
docker compose run --rm --no-deps backend python -m src.cli.check_consistency --assistant <id>
```

O comando só lê. Cada divergência sai no log como `consistency.divergence` (documento, trechos
esperados e encontrados) ou `consistency.orphan_points` (trechos de documento que o banco não
conhece); o resumo, como `consistency.finished`. O código de saída é `0` sem divergência, `1` com
divergência e `2` se o banco ou o Qdrant não responderem. Documentos pendentes ou em processamento
e assistentes em reindexação ficam de fora. Para corrigir: reprocesse ou reenvie o documento
apontado; havendo vários, ou trechos órfãos, reindexe o assistente.

### Memória Insuficiente

Modelos locais, Keycloak e worker elevam o consumo. Desative o perfil de observabilidade e
confirme a memória destinada ao Docker.
