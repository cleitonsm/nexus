# Executa a avaliacao de qualidade do RAG dentro do container do backend.
# Uso: scripts\eval.ps1 [conjunto] [opcoes do comando]
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$dataset = "nexus-docs"
$extra = @($args)
if ($extra.Count -gt 0 -and -not "$($extra[0])".StartsWith("--")) {
    $dataset = "$($extra[0])"
    if ($extra.Count -gt 1) { $extra = $extra[1..($extra.Count - 1)] } else { $extra = @() }
}

# O conjunto ampliado tem perguntas sobre documentos DOCX com tabelas
# (backend/tests/evaluation/fixtures) e usa um assistente proprio, para nao
# alterar a base do conjunto piloto.
$datasetArgs = @()
if ($dataset -eq "nexus-docs-ampliado") {
    $datasetArgs = @("--assistant-name", "Nexus Docs Ampliado (avaliacao)", "--seed-dir", "/app/evaluation/fixtures")
}
# SPEC-012: leis e regulamentos ficticios (backend/tests/evaluation/fixtures/normativo),
# tambem com assistente proprio.
if ($dataset -eq "normativo-ficticio") {
    $datasetArgs = @("--assistant-name", "Nexus Normativo (avaliacao)", "--seed-dir", "/app/evaluation/fixtures/normativo")
}

$commit = "unknown"
try {
    $resolved = git rev-parse --short HEAD 2>$null
    if ($LASTEXITCODE -eq 0 -and $resolved) { $commit = $resolved }
} catch {
    $commit = "unknown"
}

docker compose run --rm --no-deps `
    -e "GIT_COMMIT=$commit" `
    -v ./backend/tests/evaluation:/app/evaluation `
    -v ./docs:/app/seed:ro `
    backend python -m src.cli.evaluate `
    --dataset "/app/evaluation/datasets/$dataset.jsonl" `
    --reports-dir /app/evaluation/reports `
    --seed-dir /app/seed/negocio `
    --seed-dir /app/seed/arquitetura `
    @datasetArgs `
    @extra

exit $LASTEXITCODE
