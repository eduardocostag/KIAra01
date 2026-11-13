[CmdletBinding()]
param(
    [ValidateSet('preview', 'production')]
    [string]$Mode = 'preview',
    [string]$Config,
    [switch]$Strict,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Arguments = @((Join-Path $PSScriptRoot 'template-quality.mjs'), '--mode', $Mode)
if ($Config) { $Arguments += @('--config', (Resolve-Path -LiteralPath $Config).Path) }
if ($Strict) { $Arguments += '--strict' }
if ($Json) { $Arguments += '--json' }

Push-Location $ProjectRoot
try {
    & node @Arguments
    exit $LASTEXITCODE
}
finally { Pop-Location }
