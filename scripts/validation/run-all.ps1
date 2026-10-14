<#
.SYNOPSIS
  Orquestrador da validacao final (V0 a V8) para Windows.

.DESCRIPTION
  Chama scripts/validation/run-all.sh pelo bash do Git for Windows (ou do WSL),
  com as mesmas opcoes: -DryRun, -From V3, -Only V4, -KeepEnv. A logica fica em um
  unico lugar (o .sh) para que as duas formas de execucao nao divirjam.
  Saida: docs/qa/relatorios/<data>/ (resumo.md e um log por item).
#>
param(
    [switch]$DryRun,
    [string]$From = "",
    [string]$Only = "",
    [switch]$KeepEnv
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

$bash = (Get-Command bash -ErrorAction SilentlyContinue).Source
if (-not $bash) {
    $candidate = Join-Path $env:ProgramFiles "Git\bin\bash.exe"
    if (Test-Path $candidate) { $bash = $candidate }
}
if (-not $bash) {
    Write-Error "bash nao encontrado. Instale o Git for Windows ou use o WSL."
    exit 2
}

$arguments = @("scripts/validation/run-all.sh")
if ($DryRun) { $arguments += "--dry-run" }
if ($From) { $arguments += @("--from", $From) }
if ($Only) { $arguments += @("--only", $Only) }
if ($KeepEnv) { $arguments += "--keep-env" }

& $bash @arguments
exit $LASTEXITCODE
