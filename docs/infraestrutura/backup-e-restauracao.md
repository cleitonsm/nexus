# Backup e Restauração

SPEC-006 (RF-63, RNF-28) e decisões D5 e D9: backup diário em pasta local, retenção de 7 dias,
script de restauração com conferência de contagens.

## O que entra no backup

Cada execução cria uma pasta `BACKUP_PATH/<AAAAMMDDTHHMMSSZ>/` com:

| Arquivo | Conteúdo |
|---------|----------|
| `nexus.dump` | `pg_dump -Fc` do banco do Nexus (assistentes, documentos, conversas, auditoria, consumo, avaliações) |
| `keycloak.dump` | `pg_dump -Fc` do banco `keycloak` (usuários, grupos e papéis do realm) |
| `qdrant/<collection>.snapshot` | snapshot de cada collection física do Qdrant |
| `qdrant/aliases.json` | aliases das collections (`assistant_{id}` aponta para a versão ativa) |
| `documents.tar.gz` | arquivos originais do volume `documents_data` (reprocessamento, SPEC-005) |
| `counts.txt` | contagens por tabela, por collection e de arquivos, tiradas do próprio backup (D10) |
| `manifest.txt`, `SHA256SUMS` | data, banco e somas de verificação de todos os arquivos |

Nenhum segredo é gravado fora dos próprios dumps; as chaves das credenciais de LLM continuam
cifradas no banco (tabela `llm_credentials`, ADR 0005 e ADR 0013) e a chave `NEXUS_SECRETS_KEY`
**não** entra no backup. Guarde-a à parte: sem ela as chaves restauradas não podem ser decifradas
e precisam ser cadastradas de novo em "Chaves de LLM" (o teste da credencial avisa que a chave
gravada não pôde ser decifrada).

A pasta só recebe o nome final quando tudo deu certo. Uma execução interrompida deixa
`<data>.partial`, removida na execução seguinte.

## Execução diária

```bash
docker compose --profile backup up -d --build backup
docker compose logs -f backup
```

O serviço roda `backup.sh` ao subir e depois a cada `BACKUP_INTERVAL_SECONDS` (24 h). Se uma
execução falhar, tenta de novo em 1 hora. Backups mais antigos que `BACKUP_RETENTION_DAYS` são
apagados ao final de cada execução bem-sucedida; o recém-criado nunca é apagado.

Backup avulso, sem o serviço em execução:

```bash
docker compose --profile backup run --rm backup backup.sh
```

O ponto de recuperação é de no máximo 24 h (RNF-28) enquanto o computador estiver ligado com o
Docker em execução. Um backup perdido por máquina desligada é refeito na próxima subida do
serviço.

**Consistência (D10):** o backup pausa a ingestão pelo banco. Ele grava a chave
`ingestion_pause` em `app_settings`, e o worker, que a consulta antes de cada volta, deixa de
reservar jobs de ingestão e de reindexação (log `ingestion.worker.paused`). O backup espera os jobs
em andamento terminarem, por até `INGESTION_JOB_TIMEOUT_SECONDS`. Se não terminarem, o backup é
adiado e o serviço tenta de novo em 1 hora. Com a ingestão parada, copia os três armazenamentos e
libera a pausa, mesmo em caso de erro. A pausa tem prazo (`BACKUP_PAUSE_MAX_SECONDS`, 1 hora): um
backup morto sem liberá-la não trava a ingestão para sempre.

As contagens de `counts.txt` não vêm da base viva. O dump é restaurado num banco temporário
(`nexus_backup_check`, apagado em seguida), o que também prova que ele é restaurável. As collections
são contadas logo depois dos snapshots, e os arquivos, pelo próprio `documents.tar.gz`.

O que a pausa **não** cobre: o chat continua gravando conversas, mensagens, consumo e auditoria
durante o backup, o que é coerente porque o dump é um retrato consistente do banco. Uma exclusão
de documento pela tela, durante os poucos segundos dos snapshots, pode deixar uma collection com um
documento a menos que o banco; a conferência da restauração aponta a diferença.

## Restauração em ambiente limpo

1. Suba só o que a restauração usa e pare o restante:

   ```bash
   docker compose up -d postgres qdrant
   docker compose stop backend worker frontend keycloak
   ```

2. Execute, com a pasta do backup (o nome dentro de `BACKUP_PATH`):

   ```bash
   docker compose --profile backup run --rm backup restore.sh 20261008T030000Z --yes
   ```

   O script confere as somas de verificação, restaura os dois bancos (`pg_restore --clean`),
   recria cada collection a partir do snapshot, recria os aliases, devolve os documentos originais
   ao volume e compara as contagens com `counts.txt`. Contagem diferente termina com erro e mostra
   a diferença.

3. Suba tudo de novo: `docker compose up -d`. A API aplica migrações pendentes, se o backup for
   de uma versão anterior do esquema.

4. Confira (cenário "Restauração" da SPEC-006): entrar com um usuário do realm, abrir um
   assistente, ver os documentos `indexado`, abrir uma conversa antiga e fazer uma pergunta com
   citação.

## Limitações

- Destino só local (D5). Copiar `BACKUP_PATH` para outro disco ou nuvem fica como evolução.
- Collections do Qdrant que existam no destino e não estejam no backup não são apagadas; em
  ambiente limpo não há nenhuma.
- Verificação (2026-10-13): `scripts/validation/backup-scripts-check.sh` executa `backup.sh` e
  `restore.sh` contra um PostgreSQL 16 real e um Qdrant simulado. Ele confere a pausa, a espera
  pelo job em andamento, as contagens, a base restaurada sem a pausa e a recusa de um backup
  corrompido. Roda no CI (job `backup-scripts`) e passou fora do Docker.
- O ensaio completo no Docker é o CT-47: `scripts/validation/backup-restore.sh` faz o backup do
  ambiente atual, restaura num projeto Compose limpo (`nexus-ct47`, com portas deslocadas), roda a
  conferência PostgreSQL × Qdrant e uma busca nos dados restaurados, e grava as evidências em
  `docs/qa/relatorios/<data>-ct47/`. Ainda não foi executado.
