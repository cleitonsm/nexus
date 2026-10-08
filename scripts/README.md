# Scripts

Este diretório deve reunir atalhos de desenvolvimento, teste e lint.

Scripts previstos:

- `dev.sh`
- `test.sh`
- `lint.sh`

Os scripts serão adicionados quando os projetos backend e frontend forem inicializados.

## Avaliação de Qualidade

- `eval.sh` (Linux, macOS, Git Bash) e `eval.ps1` (PowerShell): executam a avaliação do RAG dentro
  do container do backend. Uso: `scripts/eval.sh [conjunto] [opções]`. Detalhes em
  `backend/tests/evaluation/README.md`.

- `quality-gate.sh`: portão de qualidade local (SPEC-006 D4). Roda os testes unitários na imagem
  do backend e a avaliação de recuperação (recall@k e MRR); com `--fidelidade`, também a avaliação
  completa, que consome o LLM. Termina com erro se houver regressão acima de
  `EVAL_REGRESSION_TOLERANCE`.

## Backup e Restauração (SPEC-006)

Executados dentro do serviço `backup` do Compose (perfil `backup`), não no computador:

- `backup.sh`: dumps do PostgreSQL (Nexus e Keycloak), snapshots do Qdrant com os aliases e cópia
  dos documentos originais, com retenção de `BACKUP_RETENTION_DAYS`.
- `restore.sh`: restauração em ambiente limpo, com conferência de contagens.
- `backup-loop.sh`: agenda do serviço (uma execução a cada 24 h).
- `backup-common.sh`: funções comuns aos dois scripts.

Procedimento em `docs/infraestrutura/backup-e-restauracao.md`.
