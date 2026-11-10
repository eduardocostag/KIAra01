param([ValidateRange(1024, 65535)][int]$Port = 3001, [switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$servicePath = Join-Path $workspaceRoot 'services/freellmapi'
$entryPath = Join-Path $servicePath 'server/dist/index.js'
$clientPath = Join-Path $servicePath 'client/dist'
$databasePath = Join-Path $workspaceRoot 'data/freellmapi/freeapi.db'
Get-Command node -ErrorAction Stop | Out-Null
if (-not (Test-Path -LiteralPath $entryPath) -or
    -not (Test-Path -LiteralPath (Join-Path $clientPath 'index.html'))) {
    throw 'Execute scripts/setup_freellmapi.ps1 para compilar servidor e painel.'
}
if ($CheckOnly) {
    Write-Output "Servidor e painel encontrados. Endpoint: http://127.0.0.1:$Port/v1"
    Write-Output "Database: $databasePath"
    exit 0
}
if ($env:ENCRYPTION_KEY -notmatch '\A[0-9a-fA-F]{64}\z') {
    throw 'Forneca ENCRYPTION_KEY no ambiente (64 hex) e reutilize a mesma chave nos proximos inicios. O launcher nao grava segredos.'
}

$previousEnvironment = @{}
foreach ($name in @('HOST', 'PORT', 'NODE_ENV', 'FREEAPI_DB_PATH', 'CLIENT_DIST')) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $databasePath) | Out-Null
Push-Location -LiteralPath $servicePath
try {
    $env:HOST = '127.0.0.1'
    $env:PORT = [string]$Port
    $env:NODE_ENV = 'production'
    $env:FREEAPI_DB_PATH = $databasePath
    $env:CLIENT_DIST = $clientPath
    Write-Output "FreeLLMAPI em http://127.0.0.1:$Port (Ctrl+C encerra)."
    & node $entryPath
    if ($LASTEXITCODE -ne 0) { throw "FreeLLMAPI encerrou com exit $LASTEXITCODE." }
} finally {
    Pop-Location
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
