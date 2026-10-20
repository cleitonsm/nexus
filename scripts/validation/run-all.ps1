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

# Prefere o bash do Git for Windows. O C:\Windows\System32\bash.exe e o lancador do WSL
# e falha ("execvpe(/bin/bash) failed") quando nao ha distribuicao instalada.
# NEXUS_BASH permite apontar outro bash.
$bash = $env:NEXUS_BASH
if (-not $bash) {
    $candidates = @(
        "$env:ProgramFiles\Git\bin\bash.exe",
        "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
    )
    $git = (Get-Command git -ErrorAction SilentlyContinue).Source
    if ($git) { $candidates += (Join-Path (Split-Path (Split-Path $git)) "bin\bash.exe") }
    $bash = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
if (-not $bash) {
    $found = (Get-Command bash -ErrorAction SilentlyContinue).Source
    if ($found -and $found -notlike "*\System32\bash.exe") { $bash = $found }
}
if (-not $bash) {
    Write-Error "bash do Git for Windows nao encontrado. Instale o Git for Windows ou defina NEXUS_BASH."
    exit 2
}
Write-Host "bash: $bash"

$arguments = @("scripts/validation/run-all.sh")
if ($DryRun) { $arguments += "--dry-run" }
if ($From) { $arguments += @("--from", $From) }
if ($Only) { $arguments += @("--only", $Only) }
if ($KeepEnv) { $arguments += "--keep-env" }

& $bash @arguments
exit $LASTEXITCODE
