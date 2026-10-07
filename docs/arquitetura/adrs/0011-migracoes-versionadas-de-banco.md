# ADR 0011: Migrações Versionadas de Banco de Dados

## Status

Proposta.

## Contexto

O esquema do banco é criado na subida da API por `Base.metadata.create_all`, complementado por uma
função que adiciona colunas ausentes. O diretório `infrastructure/database/migrations` contém
arquivos SQL numerados que não são aplicados automaticamente. A evolução RAG Enterprise acrescenta
tabelas e colunas em quase todas as fases, e alterações manuais deixam de ser sustentáveis.

## Decisão

1. Adotar migrações versionadas e reversíveis com Alembic, aplicadas na subida do ambiente antes
   de a API aceitar requisições.
2. Converter o esquema atual em uma migração inicial equivalente aos arquivos SQL existentes.
3. Remover o `create_all` e a função de colunas incrementais do ciclo de vida da API.
4. Exigir que toda alteração de esquema venha acompanhada de sua migração e do respectivo teste.

## Consequências

- O esquema passa a ter histórico e pode ser revertido.
- A subida do ambiente ganha uma etapa de migração.
- Bancos já existentes precisam ser marcados na versão inicial antes de receber novas migrações.
- Acrescenta-se uma dependência ao backend.

## Alternativas Consideradas

- **Continuar com `create_all`:** não altera tabelas existentes nem permite reversão.
- **Executor próprio para os arquivos SQL já existentes:** evita a dependência, mas obriga a manter
  controle de versão e reversão por conta própria.
