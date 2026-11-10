$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonWindowless = Join-Path (Split-Path -Parent $Python) "pythonw.exe"
$RunnerScript = Join-Path $PSScriptRoot "run_whatsapp_web.py"
$EnvironmentFile = Join-Path $ProjectRoot "apps\web\.env.local"
$DataDirectory = Join-Path $ProjectRoot "data\whatsapp-web"

foreach ($requiredPath in @($Python, $PythonWindowless, $RunnerScript)) {
    if (!(Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Arquivo necessário não encontrado: $requiredPath"
    }
}

$allowedKeys = @(
    "KIARA_WHATSAPP_OLLAMA_MODEL",
    "KIARA_WHATSAPP_OLLAMA_URL"
)
foreach ($line in $(if (Test-Path -LiteralPath $EnvironmentFile) { Get-Content -LiteralPath $EnvironmentFile })) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$' -and $allowedKeys -contains $Matches[1]) {
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($Matches[1], $value, "Process")
    }
}

New-Item -ItemType Directory -Force -Path $DataDirectory | Out-Null
$arguments = @(
    "`"$RunnerScript`"",
    "--chrome-extension",
    "--api-url",
    "`"https://kiara-api-rouge.vercel.app`""
)
$process = Start-Process -FilePath $PythonWindowless `
    -ArgumentList $arguments `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -PassThru

if ($process.HasExited -and $process.ExitCode -ne 0) {
    throw "O executor não conseguiu iniciar. Verifique a configuração local da Kiara."
}
