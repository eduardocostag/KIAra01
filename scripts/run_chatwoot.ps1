param([ValidateSet('Start', 'Stop', 'Status')][string]$Action = 'Start', [switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$composePath = Join-Path $workspaceRoot 'infra/chatwoot/compose.yaml'
if (-not (Test-Path -LiteralPath $composePath)) { throw 'Compose da Kiara nao encontrado.' }
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($CheckOnly) {
    Write-Output "Compose encontrado. Docker disponivel no PATH: $([bool]$docker)"
    Write-Output 'Endpoint planejado: http://127.0.0.1:3005; nenhuma conexao ou container foi iniciado.'
    exit 0
}
if (-not $docker) { throw 'Instale Docker Desktop com engine Linux e Docker Compose v2.' }
function Assert-ExitCode([string]$Description) {
    if ($LASTEXITCODE -ne 0) { throw "$Description falhou (exit $LASTEXITCODE)." }
}
$names = @('CHATWOOT_SECRET_KEY_BASE', 'CHATWOOT_POSTGRES_PASSWORD', 'CHATWOOT_REDIS_PASSWORD')
if ($Action -eq 'Start') {
    if ($env:CHATWOOT_SECRET_KEY_BASE -notmatch '\A[a-zA-Z0-9]{64,}\z') {
        throw 'Forneca CHATWOOT_SECRET_KEY_BASE com pelo menos 64 caracteres alfanumericos no ambiente.'
    }
    foreach ($name in $names[1..2]) {
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if (-not $value -or $value.Length -lt 24 -or $value -match '[\r\n]') {
            throw "Forneca $name com pelo menos 24 caracteres, sem quebras de linha, no ambiente."
        }
    }
    & docker compose --env-file NUL -f $composePath config --quiet
    Assert-ExitCode 'Validar Compose'
    & docker compose --env-file NUL -f $composePath up -d --wait postgres redis
    Assert-ExitCode 'Iniciar Postgres e Redis'
    & docker compose --env-file NUL -f $composePath run --rm rails bundle exec rails db:chatwoot_prepare
    Assert-ExitCode 'Preparar banco Chatwoot'
    & docker compose --env-file NUL -f $composePath up -d rails sidekiq
    Assert-ExitCode 'Iniciar Chatwoot'
    Write-Output 'Chatwoot iniciado em http://127.0.0.1:3005. Verifique o onboarding e configure sua conta/canais.'
} else {
    # Inspection/stopping require no secrets; placeholders only satisfy Compose parsing.
    $previousEnvironment = @{}
    foreach ($name in $names) {
        $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        if (-not $previousEnvironment[$name]) {
            [Environment]::SetEnvironmentVariable($name, 'unused-inspection-placeholder', 'Process')
        }
    }
    try {
        if ($Action -eq 'Stop') {
            & docker compose --env-file NUL -f $composePath stop
            Assert-ExitCode 'Parar Chatwoot sem remover volumes'
        } else {
            & docker compose --env-file NUL -f $composePath ps
            Assert-ExitCode 'Consultar containers Chatwoot'
        }
    } finally {
        foreach ($name in $previousEnvironment.Keys) {
            [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
        }
    }
}
