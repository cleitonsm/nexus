-- Papel somente leitura para o MCP de Postgres do Claude Code.
-- Apenas para o banco LOCAL de desenvolvimento (dados ficticios).
-- Uso: docker compose exec -T postgres psql -U nexus -d nexus < .claude/mcp/readonly-role.sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_readonly') THEN
    CREATE ROLE nexus_readonly LOGIN PASSWORD 'nexus_readonly';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE nexus TO nexus_readonly;
GRANT USAGE ON SCHEMA public TO nexus_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nexus_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE nexus IN SCHEMA public GRANT SELECT ON TABLES TO nexus_readonly;
ALTER ROLE nexus_readonly SET default_transaction_read_only = on;
