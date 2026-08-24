$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m ruff check app tests
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm kiara.spec
$Artifact = Join-Path $ProjectRoot "dist\Kiara.exe"
$Signature = Get-AuthenticodeSignature -LiteralPath $Artifact
if ($Signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    if ($env:KIARA_ALLOW_UNSIGNED_DEV_BUILD -eq "1") {
        Write-Warning "DEV ONLY: Kiara.exe is not Authenticode-signed and must not be distributed."
    } else {
        throw "Release blocked: Kiara.exe must have a valid Authenticode signature. Set KIARA_ALLOW_UNSIGNED_DEV_BUILD=1 only for a local non-distributable build."
    }
}
Write-Host "Artifact: $ProjectRoot\dist\Kiara.exe"
