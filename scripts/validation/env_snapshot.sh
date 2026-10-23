#!/usr/bin/env bash
# Registra o ambiente da validacao (V0): commit, hardware, Docker, imagens e modelos.
# Uso: scripts/validation/env_snapshot.sh [arquivo_de_saida.md]
# So le e imprime; nao altera nada. Nao grava variaveis de ambiente nem segredos.
set -u

out="${1:-}"
root="$(cd "$(dirname "$0")/../.." && pwd)"

# Imprime a saida do comando ou "indisponivel" (sem sobras de uma falha parcial).
try() {
  local result
  if result="$("$@" 2>/dev/null)" && [ -n "$result" ]; then echo "$result"; else echo indisponível; fi
}

snapshot() {
  echo "# Ambiente da validação"
  echo
  echo "- Data (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- Commit: $(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo desconhecido)" \
       "($(git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?'))"
  echo "- Etiqueta: $(git -C "$root" describe --tags --exact-match 2>/dev/null || echo 'sem etiqueta')"
  echo "- Arquivos alterados na árvore: $(git -C "$root" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  echo
  echo "## Máquina"
  echo "- Sistema: $(uname -srm)"
  if command -v nproc >/dev/null 2>&1; then echo "- CPUs: $(nproc)"; fi
  if [ -r /proc/cpuinfo ]; then
    echo "- Modelo da CPU: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ //')"
  fi
  if [ -r /proc/meminfo ]; then
    echo "- Memória total: $(awk '/MemTotal/ {printf "%.1f GiB", $2/1048576}' /proc/meminfo)"
  fi
  echo
  echo "## Docker"
  if command -v docker >/dev/null 2>&1; then
    echo "- Servidor: $(try docker version --format '{{.Server.Version}}')"
    echo "- Compose: $(try docker compose version --short)"
    echo "- CPUs do Docker: $(try docker info --format '{{.NCPU}}')"
    echo "- Memória do Docker (bytes): $(try docker info --format '{{.MemTotal}}')"
    echo
    echo "### Imagens do projeto"
    docker compose -f "$root/compose.yaml" images 2>/dev/null | sed 's/^/    /' || true
  else
    echo "- Docker indisponível."
  fi
  echo
  echo "## Modelos e parâmetros (de .env.example, sem ler .env)"
  grep -E '^(EMBEDDING_MODEL_NAME|EMBEDDING_VECTOR_SIZE|RERANKER_MODEL_NAME|LLM_MODEL|CHUNK_|RETRIEVAL_|UPLOAD_MAX_BYTES|INGESTION_)' \
    "$root/.env.example" 2>/dev/null | sed 's/^/    /' || true
}

if [ -n "$out" ]; then
  mkdir -p "$(dirname "$out")"
  snapshot > "$out"
  echo "Ambiente registrado em $out"
else
  snapshot
fi
