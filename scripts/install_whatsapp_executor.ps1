param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$Protocol = "HKCU:\Software\Classes\kiara-whatsapp"

if ($Uninstall) {
    if (Test-Path -LiteralPath $Protocol) {
        Remove-Item -LiteralPath $Protocol -Recurse -Force
    }
    Write-Host "Integração local do WhatsApp removida."
    exit 0
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Runner = Join-Path $ProjectRoot "scripts\run_whatsapp_web.py"
$EnvironmentFile = Join-Path $ProjectRoot "apps\web\.env.local"
$ExtensionDirectory = Join-Path $ProjectRoot "extensions\kiara-whatsapp"
$Handler = Join-Path $PSScriptRoot "launch_whatsapp_executor.ps1"
$VbsHandler = Join-Path $PSScriptRoot "launch_whatsapp_executor.vbs"

foreach ($requiredPath in @($Python, $Runner, $EnvironmentFile, (Join-Path $ExtensionDirectory "manifest.json"))) {
    if (!(Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Arquivo necessário não encontrado: $requiredPath"
    }
}

$PythonWindowless = Join-Path (Split-Path -Parent $Python) "pythonw.exe"
if (!(Test-Path -LiteralPath $PythonWindowless -PathType Leaf)) {
    throw "pythonw.exe não foi encontrado na instalação local do Python."
}

$envContents = Get-Content -LiteralPath $EnvironmentFile -Raw
foreach ($key in @("NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY")) {
    if ($envContents -notmatch "(?m)^\s*$([regex]::Escape($key))\s*=\s*\S+") {
        throw "A variável pública $key não foi encontrada em apps\web\.env.local."
    }
}

$command = '"{0}" //B //Nologo "{1}" "{2}"' -f (Join-Path $env:SystemRoot "System32\wscript.exe"), $VbsHandler, $Handler
New-Item -Path $Protocol -Force | Out-Null
Set-Item -LiteralPath $Protocol -Value "URL:Kiara WhatsApp executor"
New-ItemProperty -LiteralPath $Protocol -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
$commandKey = Join-Path $Protocol "shell\open\command"
New-Item -Path $commandKey -Force | Out-Null
Set-Item -LiteralPath $commandKey -Value $command

Write-Host "Executor registrado para este usuário do Windows."
Write-Host "Instale a extensão uma vez: Chrome > chrome://extensions > Modo do desenvolvedor > Carregar sem compactação."
Write-Host "Pasta da extensão: $ExtensionDirectory"
Write-Host "Depois, no site Kiara, clique em 'Analisar WhatsApp no Chrome'."
