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
| `counts.txt` | contagens por tabela, por collection e de arquivos, para a conferência |
| `manifest.txt`, `SHA256SUMS` | data, banco e somas de verificação de todos os arquivos |

Nenhum segredo é gravado fora dos próprios dumps; a API key do LLM continua cifrada no banco
(ADR 0005) e a chave `NEXUS_SECRETS_KEY` **não** entra no backup. Guarde-a à parte: sem ela a API
key restaurada não pode ser decifrada e precisa ser cadastrada de novo.

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

**Consistência:** o `pg_dump` é consistente por banco; o snapshot do Qdrant é tirado logo depois.
Uma ingestão concluída entre os dois pode deixar o Qdrant um documento à frente do banco. Para um
backup exato, pare o `worker` antes (`docker compose stop worker`).

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
- O procedimento não foi executado até 2026-10-08: só a sintaxe dos scripts foi verificada. O
  ensaio completo é o CT-47 da campanha de validação final.
