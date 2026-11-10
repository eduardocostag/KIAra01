param([switch]$CheckOnly, [switch]$DownloadOnly)

$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$servicePath = Join-Path $workspaceRoot 'services/chatwoot'
$composePath = Join-Path $workspaceRoot 'infra/chatwoot/compose.yaml'
$pinnedCommit = 'caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82'
$repositoryUrl = 'https://github.com/chatwoot/chatwoot.git'

function Assert-ExitCode([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action falhou (exit $LASTEXITCODE)." }
}

Get-Command git -ErrorAction Stop | Out-Null
if (-not (Test-Path -LiteralPath $servicePath)) {
    if ($CheckOnly) { throw 'Chatwoot ainda nao foi baixado; execute setup_chatwoot.ps1 -DownloadOnly.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $servicePath) | Out-Null
    & git -c http.sslBackend=openssl clone --depth 1 --branch v4.19.1 $repositoryUrl $servicePath
    Assert-ExitCode 'Baixar Chatwoot'
}
if (-not (Test-Path -LiteralPath (Join-Path $servicePath '.git'))) {
    throw 'services/chatwoot existente nao e checkout Git; nenhum arquivo foi sobrescrito.'
}
$origin = (& git -C $servicePath remote get-url origin).Trim()
Assert-ExitCode 'Verificar origem'
$headCommit = (& git -C $servicePath rev-parse HEAD).Trim()
Assert-ExitCode 'Verificar commit'
$changes = & git -C $servicePath status --porcelain --untracked-files=normal
Assert-ExitCode 'Verificar alteracoes'
if ($origin.TrimEnd('/') -notin @($repositoryUrl, $repositoryUrl.Substring(0, $repositoryUrl.Length - 4)) -or
    $headCommit -ne $pinnedCommit -or $changes) {
    throw 'Checkout divergente ou alterado; preserve/revise services/chatwoot antes de continuar.'
}
if (-not (Test-Path -LiteralPath $composePath)) { throw 'Compose da Kiara nao encontrado.' }
Write-Output "Checkout Chatwoot CE validado: v4.19.1 ($pinnedCommit)."
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($CheckOnly -or $DownloadOnly) {
    Write-Output "Docker disponivel no PATH: $([bool]$docker)"
    Write-Output 'Containers e banco nao foram iniciados.'
    exit 0
}
if (-not $docker) { throw 'Instale Docker Desktop com engine Linux e Docker Compose v2; checkout ja foi preparado.' }
& docker compose version
Assert-ExitCode 'Verificar Docker Compose'
# Image pull needs no secrets. Preserve caller variables and never materialize an .env.
$previousEnvironment = @{}
foreach ($name in @('CHATWOOT_SECRET_KEY_BASE', 'CHATWOOT_POSTGRES_PASSWORD', 'CHATWOOT_REDIS_PASSWORD')) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    if (-not $previousEnvironment[$name]) {
        [Environment]::SetEnvironmentVariable($name, 'unused-image-pull-placeholder', 'Process')
    }
}
try {
    & docker compose --env-file NUL -f $composePath config --quiet
    Assert-ExitCode 'Validar Compose'
    & docker compose --env-file NUL -f $composePath pull
    Assert-ExitCode 'Baixar imagens fixadas'
} finally {
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
Write-Output 'Imagens preparadas. Forneca os segredos no ambiente e execute scripts/run_chatwoot.ps1.'
