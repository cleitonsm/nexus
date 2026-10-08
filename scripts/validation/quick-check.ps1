# Teste rapido no Docker (etapa E1 do docs/plano-de-conclusao.md).
#
# Sobe o ambiente, espera os healthchecks, confere migracoes, rotas basicas e
# logs, e grava as evidencias em docs/qa/relatorios/<data>-e1/. As etapas que
# exigem o navegador ficam num checklist (checklist.md) para preencher a mao.
#
# Uso (na raiz do repositorio):
#   powershell -ExecutionPolicy Bypass -File scripts\validation\quick-check.ps1
#   ... -NoBuild          reaproveita as imagens ja construidas
#   ... -TimeoutMinutes 20
param(
    [switch]$NoBuild,
    [int]$TimeoutMinutes = 15
)
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..\..")

$stamp = Get-Date -Format "yyyy-MM-dd"
$out = Join-Path "docs\qa\relatorios" "$stamp-e1"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$summary = New-Object System.Collections.Generic.List[string]
$failures = 0

function Add-Result([string]$step, [bool]$ok, [string]$detail) {
    $mark = if ($ok) { "OK  " } else { "FALHA" }
    $line = "| $step | $mark | $detail |"
    $script:summary.Add($line)
    if (-not $ok) { $script:failures++ }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host "[$mark] $step - $detail" -ForegroundColor $color
}

# 1. Ambiente -----------------------------------------------------------------
$commit = (git rev-parse --short HEAD 2>$null)
$branch = (git rev-parse --abbrev-ref HEAD 2>$null)
$dirty = (git -c core.autocrlf=true status --porcelain 2>$null | Measure-Object).Count
@(
    "commit: $commit ($branch), arquivos alterados: $dirty",
    "data: $(Get-Date -Format o)",
    "docker: $(docker version --format '{{.Server.Version}}' 2>$null)",
    "compose: $(docker compose version --short 2>$null)",
    "cpus/mem docker: $(docker info --format '{{.NCPU}} CPUs, {{.MemTotal}} bytes' 2>$null)"
) | Set-Content -Encoding utf8 (Join-Path $out "00-ambiente.txt")
Add-Result "Ambiente" $true "commit $commit"

# 2. Subida -------------------------------------------------------------------
$sw = [System.Diagnostics.Stopwatch]::StartNew()
if ($NoBuild) {
    docker compose up -d *> (Join-Path $out "01-up.log")
} else {
    docker compose up -d --build *> (Join-Path $out "01-up.log")
}
$upOk = ($LASTEXITCODE -eq 0)
Add-Result "docker compose up" $upOk "codigo $LASTEXITCODE (ver 01-up.log)"

# 3. Healthchecks -------------------------------------------------------------
$expected = @("backend", "worker", "frontend", "postgres", "qdrant", "keycloak")
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$state = @{}
do {
    Start-Sleep -Seconds 10
    $raw = docker compose ps --all --format json 2>$null
    $items = @()
    if ($raw) {
        $text = ($raw -join "`n").Trim()
        if ($text.StartsWith("[")) { $items = $text | ConvertFrom-Json }
        else { $items = $raw | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json } }
    }
    $state = @{}
    foreach ($i in $items) { $state[$i.Service] = "$($i.State)/$($i.Health)" }
    $pending = $expected | Where-Object {
        $s = $state[$_]
        -not $s -or -not ($s -like "running/healthy" -or ($_ -eq "worker" -and $s -like "running/*"))
    }
} while ($pending -and (Get-Date) -lt $deadline)
$sw.Stop()
$elapsed = [int]$sw.Elapsed.TotalSeconds
$detail = ($expected | ForEach-Object { "$_=$($state[$_])" }) -join ", "
Add-Result "Servicos saudaveis" (-not $pending) "$elapsed s ate saudavel; $detail"

# 4. Migracoes ----------------------------------------------------------------
$alembic = docker compose exec -T backend alembic current 2>&1
$alembic | Set-Content -Encoding utf8 (Join-Path $out "02-alembic.txt")
Add-Result "alembic current (head)" (($alembic -join " ") -match "\(head\)") (($alembic | Select-Object -Last 1) -as [string])

# 5. Dependencias -------------------------------------------------------------
docker compose exec -T backend pip freeze 2>&1 | Set-Content -Encoding utf8 (Join-Path $out "03-pip-freeze.txt")
$req = Get-Content "backend\requirements.txt" | Where-Object { $_ -match "==" } | ForEach-Object { $_.Trim().ToLower() }
$frozen = Get-Content (Join-Path $out "03-pip-freeze.txt") | ForEach-Object { $_.Trim().ToLower() }
$missing = $req | Where-Object { $frozen -notcontains $_ }
Add-Result "requirements x pip freeze" (-not $missing) ("divergencias: " + (($missing | Select-Object -First 5) -join ", "))

# 6. Rotas basicas ------------------------------------------------------------
function Get-Status([string]$url) {
    try { return (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10).StatusCode }
    catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode } else { return 0 } }
}
$backendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { 8000 }
$frontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { 4200 }
$checks = @(
    @{ name = "API /health"; url = "http://localhost:$backendPort/health"; want = 200 },
    @{ name = "API /assistants sem token"; url = "http://localhost:$backendPort/assistants"; want = 401 },
    @{ name = "Frontend /health"; url = "http://localhost:$frontendPort/health"; want = 200 },
    @{ name = "Nginx /api/metrics bloqueado"; url = "http://localhost:$frontendPort/api/metrics"; want = 404 },
    @{ name = "Keycloak realm nexus"; url = "http://localhost:8080/realms/nexus/.well-known/openid-configuration"; want = 200 }
)
foreach ($c in $checks) {
    $code = Get-Status $c.url
    Add-Result $c.name ($code -eq $c.want) "HTTP $code (esperado $($c.want))"
}

# 7. Logs ---------------------------------------------------------------------
docker compose logs --no-color --timestamps backend worker keycloak qdrant frontend *> (Join-Path $out "04-logs.txt")
$logText = Get-Content (Join-Path $out "04-logs.txt")
$tracebacks = ($logText | Select-String -Pattern "Traceback|CRITICAL|\"level\": \"ERROR\"").Count
$compat = $logText | Select-String -Pattern "incompatib|version.*(client|server)|qdrant_client.*warn" | Select-Object -First 3
Add-Result "Erros nos logs" ($tracebacks -eq 0) "$tracebacks ocorrencias de Traceback/ERROR"
Add-Result "Aviso de versao do Qdrant" ($null -eq $compat) ((($compat | ForEach-Object { $_.Line.Trim() }) -join " / ") + "")

# 8. Checklist manual ---------------------------------------------------------
@"
# Checklist manual do teste rapido (E1) - $stamp, commit $commit

Marque cada item e anote o que aconteceu quando falhar. Usuarios do realm: senha ``nexus-dev``.

- [ ] Abrir http://localhost:$frontendPort e entrar como ``admin.nexus`` (vai ao Keycloak e volta)
- [ ] Criar um assistente e vincular o grupo ``rh`` em "Assistentes"
- [ ] Entrar como ``curadora.rh`` e enviar um PDF com texto: Pendente -> Processando -> Indexado sem recarregar a pagina
- [ ] Enviar o mesmo arquivo de novo: aviso de duplicidade
- [ ] Entrar como ``usuario.rh`` e perguntar algo do documento: texto aparece em partes, com fontes [n] ao final
- [ ] Abrir uma fonte e conferir o trecho
- [ ] Marcar a resposta como "nao util" com comentario; como ``curadora.rh``, ver em "Avaliacoes"
- [ ] Entrar como ``usuario.financeiro``: o assistente de RH nao aparece
- [ ] Como ``admin.nexus``, abrir "Consumo e limites" e "Auditoria"
- [ ] ``docker compose restart`` e conferir que a conversa continua la

Observacoes:

"@ | Set-Content -Encoding utf8 (Join-Path $out "checklist.md")

# Resumo ----------------------------------------------------------------------
$header = @(
    "# Teste rapido no Docker (E1) - $stamp",
    "",
    "Commit ``$commit``; subida ate saudavel em $elapsed s; falhas automaticas: $failures.",
    "",
    "| Etapa | Resultado | Detalhe |",
    "|-------|-----------|---------|"
)
($header + $summary) | Set-Content -Encoding utf8 (Join-Path $out "RESUMO.md")

Write-Host ""
Write-Host "Evidencias em $out. Falhas automaticas: $failures." -ForegroundColor Cyan
Write-Host "Agora faca o checklist manual em $out\checklist.md." -ForegroundColor Cyan
exit $failures
