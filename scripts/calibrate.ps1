# Varre a nota minima de relevancia (CT-22) sobre a base do piloto, sem chamar o LLM.
# Requer que scripts\eval.ps1 ja tenha indexado o piloto.
# Uso: scripts\calibrate.ps1 [conjunto] [opcoes do comando]
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$dataset = "nexus-docs"
$extra = @($args)
if ($extra.Count -gt 0 -and -not "$($extra[0])".StartsWith("--")) {
    $dataset = "$($extra[0])"
    if ($extra.Count -gt 1) { $extra = $extra[1..($extra.Count - 1)] } else { $extra = @() }
}

$datasetArgs = @()
if ($dataset -eq "nexus-docs-ampliado") {
    $datasetArgs = @("--assistant-name", "Nexus Docs Ampliado (avaliacao)")
}
if ($dataset -eq "normativo-ficticio") {
    $datasetArgs = @("--assistant-name", "Nexus Normativo (avaliacao)")
}

docker compose run --rm --no-deps `
    -v ./backend/tests/evaluation:/app/evaluation `
    backend python -m src.cli.calibrate_relevance `
    --dataset "/app/evaluation/datasets/$dataset.jsonl" `
    --output "/app/evaluation/reports/$dataset/calibracao.json" `
    @datasetArgs `
    @extra

exit $LASTEXITCODE
