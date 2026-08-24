[CmdletBinding()]
param(
    [string]$Version = "",
    [string]$IsccPath = "",
    [switch]$AllowUnsignedDev,
    [string]$CertificateThumbprint = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Executable = Join-Path $ProjectRoot "dist\Kiara.exe"
$InstallerDirectory = Join-Path $ProjectRoot "dist\installer"
$IssFile = Join-Path $ProjectRoot "installer\kiara.iss"

if (-not $Version) {
    $Pyproject = Get-Content -LiteralPath (Join-Path $ProjectRoot "pyproject.toml") -Raw
    $Match = [regex]::Match($Pyproject, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $Match.Success) { throw "Não foi possível ler a versão de pyproject.toml." }
    $Version = $Match.Groups[1].Value
}
if ($Version -notmatch '^\d+\.\d+\.\d+(?:\.\d+)?$') {
    throw "A versão do instalador deve ser numérica e compatível com VersionInfo (ex.: 1.2.3)."
}
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    throw "Executável ausente: $Executable. Execute scripts\build-windows.ps1 primeiro."
}

function Invoke-SignFile([string]$Path) {
    if (-not $CertificateThumbprint) { return }
    $SignTool = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if (-not $SignTool) { throw "signtool.exe não foi encontrado no PATH." }
    & $SignTool.Source sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $Path
    if ($LASTEXITCODE -ne 0) { throw "Falha ao assinar $Path." }
}

Invoke-SignFile $Executable
$ExecutableSignature = Get-AuthenticodeSignature -LiteralPath $Executable
if ($ExecutableSignature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -and -not $AllowUnsignedDev) {
    throw "Release bloqueada: Kiara.exe não possui assinatura Authenticode válida. Use -AllowUnsignedDev somente para build local não distribuível."
}

if (-not $IsccPath) {
    $Command = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
    if ($Command) { $IsccPath = $Command.Source }
}
if (-not $IsccPath) {
    $Candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $IsccPath = $Candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
}
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath -PathType Leaf)) {
    throw "Inno Setup 6 (ISCC.exe) não encontrado. Instale-o ou informe -IsccPath."
}

New-Item -ItemType Directory -Path $InstallerDirectory -Force | Out-Null
& $IsccPath "/DMyAppVersion=$Version" "/DSourceExe=$Executable" "/DOutputDirectory=$InstallerDirectory" $IssFile
if ($LASTEXITCODE -ne 0) { throw "A compilação do instalador falhou." }

$Installer = Join-Path $InstallerDirectory "Kiara-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) { throw "Instalador esperado não foi criado: $Installer" }
Invoke-SignFile $Installer
$InstallerSignature = Get-AuthenticodeSignature -LiteralPath $Installer
if ($InstallerSignature.Status -ne [System.Management.Automation.SignatureStatus]::Valid -and -not $AllowUnsignedDev) {
    throw "Release bloqueada: o instalador não possui assinatura Authenticode válida."
}

$Hash = Get-FileHash -LiteralPath $Installer -Algorithm SHA256
Write-Host "Installer: $Installer"
Write-Host "SHA-256: $($Hash.Hash)"
if ($AllowUnsignedDev -and $InstallerSignature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    Write-Warning "DEV ONLY: instalador não assinado; não distribua este artefato."
}
