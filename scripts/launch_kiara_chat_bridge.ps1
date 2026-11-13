param([int]$Port = 3008, [switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$kiaraRoot = Split-Path -Parent $PSScriptRoot
$kiaraPython = Join-Path $kiaraRoot '.venv\Scripts\python.exe'
$kiaraRunner = Join-Path $PSScriptRoot 'run_kiara_chat.py'
$kiaraLogs = Join-Path $kiaraRoot '.cache\kiara-chat'
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Porta inválida.' }

Push-Location -LiteralPath $kiaraRoot
try {
    & $kiaraPython $kiaraRunner --check-only
    if ($LASTEXITCODE -ne 0) { throw 'Revise a configuração do provedor no .env.local. Nenhuma chave foi exibida.' }
    if ($CheckOnly) { return }
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    if ($listeners | Where-Object { $_.Port -eq $Port }) {
        throw "A porta $Port já está ocupada. Nenhum processo foi interrompido."
    }
    New-Item -ItemType Directory -Force -Path $kiaraLogs | Out-Null
    $kiaraBridgeProcess = Start-Process -FilePath $kiaraPython -ArgumentList @('-u', ('"' + $kiaraRunner + '"'), '--port', $Port) -WorkingDirectory $kiaraRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $kiaraLogs "bridge-$Port.stdout.log") -RedirectStandardError (Join-Path $kiaraLogs "bridge-$Port.stderr.log") -PassThru
    $kiaraBridgeProcess.Id | Set-Content -LiteralPath (Join-Path $kiaraLogs "bridge-$Port.pid") -Encoding ascii
    Write-Output "Ponte Kiara iniciada na porta $Port; PID $($kiaraBridgeProcess.Id)."
} finally {
    Pop-Location
}
