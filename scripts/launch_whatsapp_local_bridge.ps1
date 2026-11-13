param([int]$Port = 3009)

$ErrorActionPreference = "Stop"
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $workspaceRoot '.venv\Scripts\python.exe'
$runnerPath = Join-Path $PSScriptRoot 'run_whatsapp_local_bridge.py'
$logDirectory = Join-Path $workspaceRoot '.cache\whatsapp'

if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Porta inválida.' }
foreach ($requiredPath in @($pythonPath, $runnerPath)) {
  if (!(Test-Path -LiteralPath $requiredPath -PathType Leaf)) { throw 'Runtime local da Kiara não encontrado.' }
}

# Never kill a process merely because it owns a port. Reuse a healthy bridge,
# otherwise leave the existing listener intact and report the collision.
try {
  $probe = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/status" -Method Options -Headers @{Origin='https://kiaralead.vercel.app'; 'Access-Control-Request-Method'='POST'} -TimeoutSec 3
  if ($probe.StatusCode -eq 204 -and $probe.Headers['Access-Control-Allow-Origin'] -eq 'https://kiaralead.vercel.app') {
    Write-Output "A ponte da Kiara já está respondendo na porta $Port."
    exit 0
  }
} catch { }

$listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
if ($listeners | Where-Object { $_.Port -eq $Port }) { throw "A porta $Port está ocupada. Nenhum processo foi interrompido." }

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$bridgeProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-u', ('"' + $runnerPath + '"'), '--port', $Port) -WorkingDirectory $workspaceRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDirectory "bridge-$Port.stdout.log") -RedirectStandardError (Join-Path $logDirectory "bridge-$Port.stderr.log") -PassThru
$bridgeProcess.Id | Set-Content -LiteralPath (Join-Path $logDirectory "bridge-$Port.pid") -Encoding ascii
Write-Output "Ponte iniciada na porta $Port; PID $($bridgeProcess.Id)."
