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

## Evolução RAG Enterprise (Planejado)

Scripts previstos nas especificações:

- `backup.sh`: backup do PostgreSQL, snapshots do Qdrant e cópia dos documentos originais (SPEC-006).
- `restore.sh`: restauração em ambiente limpo, com conferência de contagens (SPEC-006).
