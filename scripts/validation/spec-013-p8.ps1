# Validacao da SPEC-013 no Docker (P8 do plano de implementacao).
#
# Roda, com a pilha ja no ar (docker compose up -d --build --wait):
#   1. testes de integracao do backend (inclui CT-107, CT-108, CT-109);
#   2. CT-56 varredura de vazamento (exige uma credencial de LLM cadastrada);
#   3. E2E do frontend (Playwright: CT-81 a CT-84, CT-86 a CT-88, FE-04);
#   4. CT-111 avaliacao dos tres conjuntos com a configuracao padrao.
# Grava um log por etapa e o resumo em docs/qa/relatorios/<data>-spec-013/.
# Uma etapa que falha nao interrompe as seguintes.
#
# Uso (na raiz do repositorio):
#   powershell -ExecutionPolicy Bypass -File scripts\validation\spec-013-p8.ps1
#   ... -Skip e2e,eval     pula etapas (integracao, ct56, e2e, eval)
param(
    [string[]]$Skip = @()
)
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location (Join-Path $PSScriptRoot "..\..")
$root = (Get-Location).Path

$stamp = Get-Date -Format "yyyy-MM-dd"
$outRel = "docs/qa/relatorios/$stamp-spec-013"
$out = Join-Path $root $outRel
New-Item -ItemType Directory -Force -Path $out | Out-Null
$summary = New-Object System.Collections.Generic.List[string]
$failures = 0

function Invoke-Step([string]$name, [string]$log, [scriptblock]$command) {
    Write-Host "==> $name"
    $started = Get-Date
    $path = Join-Path $script:out $log
    $global:LASTEXITCODE = 0
    & $command *>&1 | ForEach-Object { "$_" } | Tee-Object -Variable captured | Out-Host
    $code = $LASTEXITCODE
    # UTF-8: o Tee-Object do PowerShell 5.1 gravaria em UTF-16.
    $captured | Out-File -Encoding utf8 $path
    $minutes = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
    $mark = if ($code -eq 0) { "OK" } else { "FALHA ($code)" }
    if ($code -ne 0) { $script:failures++ }
    $script:summary.Add("| $name | $mark | $minutes min | $log |")
}

$commit = (git rev-parse --short HEAD) 2>$null
"commit: $commit`ndata: $(Get-Date -Format s)`n" | Out-File -Encoding utf8 (Join-Path $out "00-ambiente.txt")
docker compose ps *>&1 | Out-File -Append -Encoding utf8 (Join-Path $out "00-ambiente.txt")

$backendRun = @(
    "compose", "run", "--rm", "-e", "PYTHONPATH=/app:/app/integration",
    "-v", "./backend/tests:/app/tests",
    "-v", "./backend/tests/integration:/app/integration:ro",
    "-v", "./backend/tests/evaluation:/app/evaluation",
    "-v", "./scripts:/app/scripts:ro",
    "-v", "./$($outRel):/app/out",
    "backend"
)

if ($Skip -notcontains "integracao") {
    Invoke-Step "Testes de integracao do backend" "01-integracao.log" {
        docker @backendRun sh -c "cd /app/tests/integration && python -m unittest discover -s . -v"
    }
}

if ($Skip -notcontains "ct56") {
    Invoke-Step "CT-56 varredura de vazamento" "02-ct56.log" {
        docker @backendRun python /app/scripts/validation/leakage_scan.py --out /app/out/ct56
    }
}

if ($Skip -notcontains "e2e") {
    Invoke-Step "E2E do frontend (Playwright)" "03-e2e.log" {
        Push-Location frontend
        try { npx playwright test --reporter=list } finally { Pop-Location }
    }
}

if ($Skip -notcontains "eval") {
    foreach ($dataset in @("nexus-docs", "nexus-docs-ampliado", "normativo-ficticio")) {
        Invoke-Step "CT-111 avaliacao $dataset" "04-avaliacao-$dataset.log" {
            powershell -NoProfile -ExecutionPolicy Bypass -File scripts\eval.ps1 $dataset
        }
    }
}

$lines = @(
    "# Validacao da SPEC-013 (P8) - $stamp",
    "",
    "Commit: $commit. Falhas: $failures.",
    "",
    "| Etapa | Resultado | Duracao | Log |",
    "|---|---|---|---|"
) + $summary
$lines | Out-File -Encoding utf8 (Join-Path $out "resumo.md")
$lines | Out-Host
exit $failures
