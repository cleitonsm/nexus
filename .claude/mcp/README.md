# MCP de Postgres (somente leitura)

O servidor `postgres` do `.mcp.json` usa o pacote `postgres-mcp` em modo `restricted` (só leitura) e um papel `nexus_readonly` sem permissão de escrita. Use apenas com o banco local do Compose.

1. Instale o `uv` (fornece o `uvx`): `winget install astral-sh.uv` ou `pip install uv`.
2. Com a stack no ar, crie o papel:
   `docker compose exec -T postgres psql -U nexus -d nexus < .claude/mcp/readonly-role.sql`
3. Para outra URL, defina `NEXUS_MCP_DATABASE_URL` no ambiente (nunca aponte para um banco com documentos reais).
4. No Claude Code, aprove os servidores do projeto quando solicitado e confira com `/mcp`.
