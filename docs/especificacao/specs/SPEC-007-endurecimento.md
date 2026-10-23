# SPEC-007 — Endurecimento (P0 do cartographer)

**ID**: SPEC-20261014-007
**Status**: Aprovada em 2026-10-14 (escopo e política de fix-4 escolhidos pelo autor: "P0 do cartographer, depois E7" e "Só local, com aviso"); código entregue, validação no Docker pendente
**Origem**: `.cartographer/backlog.md`, itens fix-1 a fix-4 (prioridade P0)
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

A revisão do cartographer apontou quatro falhas de prioridade máxima: mensagens de papel
`assistant` ou `system` podem ser gravadas por quem chama a API (fix-1); o upload é lido por inteiro
na memória antes de o limite de tamanho ser verificado (fix-2); um job de ingestão ou de reindexação
cuja reserva expira continua gravando por cima do worker que o assumiu (fix-3); portas e segredos
padrão ficam expostos fora do ambiente local (fix-4).

## Decisões

| # | Escolha |
|---|---------|
| D1 | `POST /conversations/{id}/messages` aceita apenas `role = user`; os papéis `assistant` e `system` são produzidos pelo servidor. |
| D2 | O upload é recusado com 413 pelo `Content-Length` declarado (arquivo + 64 KiB de envelope) e lido em blocos até `limite + 1` byte; nunca se carrega mais que isso. |
| D3 | Dono do job = `id` + número da tentativa (`attempts`) + estado (`processando` na ingestão, `running` na reindexação). Renovação e gravação do resultado são `UPDATE` condicionais; zero linhas afetadas = reserva perdida. Sem migração: usa colunas existentes. |
| D4 | Quem perde a reserva para sem gravar documento, sem descartar trechos ou collection, sem trocar o alias e sem marcar falha: o novo dono continua. |
| D5 | Fix-4 só local, com aviso: portas publicadas em `127.0.0.1` (o frontend continua público); API e worker recusam iniciar se `APP_ENV` não for `local` e algum segredo (`NEXUS_SECRETS_KEY`, `QDRANT_API_KEY`, `POSTGRES_PASSWORD`, `KEYCLOAK_BACKEND_CLIENT_SECRET`) estiver ausente ou com o valor padrão; no ambiente local a API registra um aviso. O realm de desenvolvimento mantém os usuários de teste; senha por variável e saída do `start-dev` ficam fora deste escopo. |

## Requisitos funcionais

- RF-64: apenas mensagens `user` podem ser adicionadas diretamente a uma conversa.
- RF-65: uploads maiores que `UPLOAD_MAX_BYTES` respondem 413 sem carregar o arquivo inteiro; a leitura do assistente no envio não bloqueia o laço assíncrono.
- RF-66: a reserva dos jobs de ingestão e de reindexação é renovada durante o trabalho; escrita de quem não é mais dono é recusada.
- RF-67: fora do ambiente local, segredos padrão impedem a partida; a mensagem cita o nome da variável, nunca o valor.

## Critérios de aceite

```gherkin
Cenário: papel forjado (RF-64)
  Dado uma conversa do usuário
  Quando ele envia POST /messages com role "assistant" ou "system"
  Então a resposta é 422 e nada é gravado

Cenário: arquivo grande (RF-65)
  Dado o limite de 25 MB
  Quando o Content-Length declarado excede o limite mais o envelope, ou o fluxo passa do limite
  Então a resposta é 413 e a leitura para em, no máximo, um bloco além do limite

Cenário: dois workers (RF-66)
  Dado o worker A com a reserva expirada e o worker B que assumiu o job (tentativa 2)
  Quando A tenta renovar, concluir, repetir ou falhar o job
  Então A é recusado, o job segue com B e nenhum trecho ou alias de B é alterado

Cenário: segredo padrão (RF-67)
  Dado APP_ENV diferente de "local"
  Quando algum segredo está ausente ou com o valor padrão
  Então a API e o worker não iniciam, citando só o nome da variável
```

## Impacto arquitetural

Domínio: erro `JobOwnershipLostError`; portas `IngestionJobQueue.renew` e
`ReindexJobRepository.renew_lease` / `save_if_owner`. Aplicação: `ProcessNextIngestionJobUseCase` e
`RunReindexUseCase` renovam a reserva e param ao perdê-la. Infraestrutura: `UPDATE` condicionais
em `repositories.py`, `infrastructure/security.py`. API: `api/uploads.py`. Sem ADR novo e sem migração.

## Estratégia de testes

- Unitários: `test_access_control.py` (papel), `test_upload_reading.py`, `test_job_ownership.py`
  (dois workers simulados, ingestão e reindexação), `test_deployment_safety.py`.
- Integração: `test_access_control_api.py` (422), `test_job_ownership_storage.py` (PostgreSQL; exige o Compose).

## Riscos

- Os `UPDATE` condicionais foram verificados só por revisão e pelo dublê: SQLAlchemy não estava disponível no ambiente de desenvolvimento; o teste de PostgreSQL precisa rodar no Compose.
- A janela entre a última renovação e a gravação final é curta, não nula.
- Itens fix-5 a fix-14 do backlog continuam abertos.

## Achado complementar (E7)

Ao escrever o CT-04, constatou-se que `python -m src.cli.evaluate` não iniciava desde a SPEC-005:
montava `IngestDocumentUseCase` com um argumento que não existe mais (sem `job_queue`) e, mesmo
corrigido, mediria uma base vazia, porque o envio só cria documentos pendentes. O comando agora
envia e processa a fila com `seed_documents` (código de saída 3 se algum documento do piloto não
chegar a `indexado`; CT-62) e a avaliação ganhou a métrica `citation_coverage`.

**Ajuste de 2026-10-20 (V3 no Docker).** Com o worker da pilha no ar, que é a situação normal da V6, o worker
reservava parte dos jobs do piloto e o comando terminava com código 3 ("fila não processada por completo"); a
limpeza do teste ainda podia esbarrar num *deadlock* com o worker. Agora `seed_documents` processa os jobs
disponíveis e acompanha pelo banco os documentos que outro worker reservou, até chegarem a `indexado` ou
`falhou`, com o prazo do job de ingestão (`INGESTION_JOB_TIMEOUT_SECONDS`, 600 s, D7 da SPEC-005). A cada
volta também processa as novas tentativas que ficarem disponíveis. O código de saída 3 continua valendo para
documento `falhou` ou que não termina no prazo (CT-04, CT-62; `test_evaluation_seeding.py`).
