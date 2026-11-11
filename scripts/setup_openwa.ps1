param([switch]$CheckOnly, [switch]$DownloadOnly)

$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$servicePath = Join-Path $workspaceRoot 'services/openwa'
$pinnedCommit = '44856156e121632cac8fb6f14d14633a6c2e3794'
$repositoryUrl = 'https://github.com/rmyndharis/OpenWA.git'
function Assert-ExitCode([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit $LASTEXITCODE)." }
}
Get-Command git -ErrorAction Stop | Out-Null
Get-Command node -ErrorAction Stop | Out-Null
Get-Command npm.cmd -ErrorAction Stop | Out-Null
$nodeVersion = [version]((& node -p 'process.versions.node').Trim())
Assert-ExitCode 'Check Node'
if ($nodeVersion -lt [version]'22.19.0' -or $nodeVersion -ge [version]'25.0.0') {
    throw 'This pinned integration requires Node >=22.19 and <25.'
}
if (Test-Path -LiteralPath $servicePath) {
    if (-not (Test-Path -LiteralPath (Join-Path $servicePath '.git'))) {
        throw 'Existing services/openwa is not a Git checkout; nothing was replaced.'
    }
    $origin = (& git -C $servicePath remote get-url origin).Trim()
    Assert-ExitCode 'Check origin'
    $headCommit = (& git -C $servicePath rev-parse HEAD).Trim()
    Assert-ExitCode 'Check revision'
    $changes = & git -C $servicePath status --porcelain --untracked-files=normal
    Assert-ExitCode 'Check source changes'
    if ($origin.TrimEnd('/') -notin @($repositoryUrl, $repositoryUrl.Substring(0, $repositoryUrl.Length - 4)) -or $headCommit -ne $pinnedCommit -or $changes) {
        throw 'OpenWA checkout differs from the pinned clean source; preserve/review it before retrying.'
    }
} else {
    if ($CheckOnly) { throw 'OpenWA has not been installed.' }
    & git -c http.sslBackend=openssl clone --no-checkout $repositoryUrl $servicePath
    Assert-ExitCode 'Clone OpenWA'
    & git -C $servicePath checkout --detach $pinnedCommit
    Assert-ExitCode 'Select pinned revision'
}
if ($CheckOnly -or $DownloadOnly) {
    Write-Output "OpenWA checkout verified: $pinnedCommit"
    Write-Output "Server built: $(Test-Path -LiteralPath (Join-Path $servicePath 'dist/main.js'))"
    Write-Output "Dashboard built: $(Test-Path -LiteralPath (Join-Path $servicePath 'dashboard/dist/index.html'))"
    exit 0
}
$previousSkip = $env:PUPPETEER_SKIP_DOWNLOAD
$previousCache = $env:npm_config_cache
$previousGyp = $env:npm_config_devdir
Push-Location -LiteralPath $servicePath
try {
    # The launcher uses the installed Chrome; prevent a global browser download.
    $env:PUPPETEER_SKIP_DOWNLOAD = 'true'
    $env:npm_config_cache = Join-Path $workspaceRoot '.cache/npm-openwa'
    $env:npm_config_devdir = Join-Path $workspaceRoot '.cache/node-gyp-openwa'
    # npm 11 follows hasInstallScript in this release's lockfile and invokes
    # node-gyp for better-sqlite3, although v13 ships its native prebuilds and
    # declares gypfile:false. Install exact files, then run the reviewed OpenWA
    # postinstall explicitly instead of compiling a needless global toolchain.
    & npm.cmd ci --ignore-scripts --no-fund --no-audit
    Assert-ExitCode 'Install locked dependencies'
    & node -e "const Database=require('better-sqlite3');const db=new Database(':memory:');if(db.prepare('select 1 as ok').get().ok!==1)process.exit(1);db.close()"
    Assert-ExitCode 'Verify bundled SQLite native binding'
    & node scripts/postinstall.js
    Assert-ExitCode 'Install dashboard and apply upstream dependency patches'
    & npm.cmd run build:all
    Assert-ExitCode 'Build OpenWA and dashboard'
} finally {
    Pop-Location
    $env:PUPPETEER_SKIP_DOWNLOAD = $previousSkip
    $env:npm_config_cache = $previousCache
    $env:npm_config_devdir = $previousGyp
}
Write-Output 'OpenWA prepared. Start with scripts/run_openwa.ps1.'
