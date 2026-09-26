param(
  [Parameter(Mandatory = $true)][string]$PublicIp,
  [Parameter(Mandatory = $true)][string]$SshPrivateKey,
  [Parameter(Mandatory = $true)][string]$WorkerToken,
  [string]$SshUser = "ubuntu"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$remote = "$SshUser@$PublicIp"
$workerHost = ($PublicIp -replace '\.', '-') + ".sslip.io"
$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("kiara-browser-" + [guid]::NewGuid())

try {
  New-Item -ItemType Directory -Path $stage | Out-Null
  Copy-Item -Recurse (Join-Path $repoRoot "services/browser-worker") (Join-Path $stage "browser-worker")
  Copy-Item (Join-Path $repoRoot "infra/oracle/browser-worker/docker-compose.yml") $stage
  Copy-Item (Join-Path $repoRoot "infra/oracle/browser-worker/Caddyfile") $stage
  $profileSalt = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32)).ToLowerInvariant()
  @(
    "WORKER_HOST=$workerHost"
    "KIARA_WORKER_TOKEN=$WorkerToken"
    "KIARA_PROFILE_SALT=$profileSalt"
  ) | Set-Content -Encoding utf8 (Join-Path $stage ".env")

  ssh -i $SshPrivateKey $remote "mkdir -p /opt/kiara-browser"
  scp -i $SshPrivateKey -r "$stage/*" "${remote}:/opt/kiara-browser/"
  ssh -i $SshPrivateKey $remote "cd /opt/kiara-browser && sudo docker compose up -d --build"
  Write-Host "Worker publicado em https://$workerHost"
  Write-Host "Configure na API: KIARA_BROWSER_WORKER_URL=https://$workerHost"
  Write-Host "Configure na API: KIARA_BROWSER_WORKER_TOKEN=<o mesmo token informado>"
} finally {
  if (Test-Path $stage) { Remove-Item -Recurse -Force -LiteralPath $stage }
}

