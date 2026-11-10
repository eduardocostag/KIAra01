param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$servicePath = Join-Path $workspaceRoot 'services/freellmapi'
$pinnedCommit = '8b4c7a36e3e147bb5add2a5ba4fd95dd6f5120d3'
$repositoryUrl = 'https://github.com/tashfeenahmed/freellmapi.git'

function Assert-ExitCode([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action falhou (exit $LASTEXITCODE)." }
}

Get-Command git -ErrorAction Stop | Out-Null
Get-Command node -ErrorAction Stop | Out-Null
Get-Command npm.cmd -ErrorAction Stop | Out-Null
$nodeVersion = [version]((& node -p 'process.versions.node').Trim())
Assert-ExitCode 'Verificar Node'
if ($nodeVersion -lt [version]'20.18.0' -or $nodeVersion -ge [version]'25.0.0') {
    throw 'FreeLLMAPI requer Node >=20.18 e <25.'
}
$npmVersion = [version]((& npm.cmd --version).Trim())
Assert-ExitCode 'Verificar npm'
if ($npmVersion.Major -lt 10) { throw 'FreeLLMAPI requer npm >=10.' }

if (Test-Path -LiteralPath $servicePath) {
    if (-not (Test-Path -LiteralPath (Join-Path $servicePath '.git'))) {
        throw 'services/freellmapi existente nao e checkout Git; nenhum arquivo foi sobrescrito.'
    }
    $origin = (& git -C $servicePath remote get-url origin).Trim()
    Assert-ExitCode 'Verificar origem'
    if ($origin.TrimEnd('/') -notin @($repositoryUrl, $repositoryUrl.Substring(0, $repositoryUrl.Length - 4))) {
        throw 'Origem divergente em services/freellmapi; nenhum arquivo foi sobrescrito.'
    }
    $headCommit = (& git -C $servicePath rev-parse HEAD).Trim()
    Assert-ExitCode 'Verificar commit'
    $changes = & git -C $servicePath status --porcelain --untracked-files=normal
    Assert-ExitCode 'Verificar alteracoes'
    if ($headCommit -ne $pinnedCommit -or $changes) {
        throw 'Checkout divergente ou alterado em services/freellmapi; preserve/revise manualmente antes de continuar.'
    }
} else {
    if ($CheckOnly) { throw 'FreeLLMAPI ainda nao foi instalado.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $servicePath) | Out-Null
    & git -c http.sslBackend=openssl clone --no-checkout $repositoryUrl $servicePath
    Assert-ExitCode 'Clonar FreeLLMAPI'
    & git -C $servicePath checkout --detach $pinnedCommit
    Assert-ExitCode 'Selecionar commit fixado'
}

if ($CheckOnly) {
    Write-Output "Checkout FreeLLMAPI validado em $pinnedCommit."
    Write-Output "Servidor compilado: $(Test-Path -LiteralPath (Join-Path $servicePath 'server/dist/index.js'))"
    Write-Output "Painel compilado: $(Test-Path -LiteralPath (Join-Path $servicePath 'client/dist/index.html'))"
    exit 0
}

Push-Location -LiteralPath $servicePath
try {
    & npm.cmd ci --cache (Join-Path $workspaceRoot '.cache/npm-freellmapi')
    Assert-ExitCode 'Instalar dependencias fixadas'
    & npm.cmd run build
    Assert-ExitCode 'Compilar FreeLLMAPI'
} finally { Pop-Location }
Write-Output 'FreeLLMAPI preparado. Inicie com scripts/run_freellmapi.ps1.'
