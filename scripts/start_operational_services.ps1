<#
.SYNOPSIS
Starts Kiara's installed FreeLLMAPI and/or Chatwoot services with persistent local secrets.
.DESCRIPTION
Secrets are encrypted with Windows DPAPI for the current user. Does not install software,
register upstream providers, connect social accounts, or send messages.
.PARAMETER Service
All starts FreeLLMAPI in a hidden background process and then Chatwoot containers.
FreeLLMAPI runs in the foreground; Chatwoot starts its containers.
.PARAMETER CheckOnly
Checks local prerequisites without creating secrets, processes, or containers.
.EXAMPLE
powershell -NoProfile -File scripts/start_operational_services.ps1 -CheckOnly
.EXAMPLE
powershell -NoProfile -File scripts/start_operational_services.ps1 -Service FreeLLMAPI
#>
param(
    [ValidateSet('All', 'FreeLLMAPI', 'Chatwoot')][string]$Service = 'All',
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $workspaceRoot 'data/operational-services'
$freeLauncher = Join-Path $PSScriptRoot 'run_freellmapi.ps1'
$chatLauncher = Join-Path $PSScriptRoot 'run_chatwoot.ps1'
$freeEntry = Join-Path $workspaceRoot 'services/freellmapi/server/dist/index.js'
$freeClient = Join-Path $workspaceRoot 'services/freellmapi/client/dist/index.html'
$freeReady = [bool](Get-Command node -ErrorAction SilentlyContinue) -and
    (Test-Path -LiteralPath $freeEntry) -and (Test-Path -LiteralPath $freeClient)
$dockerReady = [bool](Get-Command docker -ErrorAction SilentlyContinue)

if ($CheckOnly) {
    Write-Output "FreeLLMAPI artifacts and Node available: $freeReady"
    Write-Output "Chatwoot Docker available: $dockerReady"
    Write-Output "Encrypted state directory: $statePath"
    Write-Output 'No secret was created or read; no service or container was started.'
    if (-not $freeReady) { Write-Output 'FreeLLMAPI fix: run scripts/setup_freellmapi.ps1.' }
    if (-not $dockerReady) { Write-Output 'Chatwoot fix: install/start Docker Desktop with Linux engine and Compose v2.' }
    exit 0
}

function Get-PersistentSecret([string]$Name, [int]$Bytes, [bool]$AllowCreate) {
    $secretPath = Join-Path $statePath "$Name.dpapi"
    $provided = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if (Test-Path -LiteralPath $secretPath) {
        try {
            $secureValue = Get-Content -LiteralPath $secretPath -Raw | ConvertTo-SecureString
            $plainValue = [System.Net.NetworkCredential]::new('', $secureValue).Password
        } catch {
            throw "Cannot decrypt saved $Name. Use the original Windows account and machine or restore its backup; the saved secret was not replaced."
        }
        if ($provided -and $provided -cne $plainValue) {
            throw "Environment $Name differs from its saved value. Remove the override or restore the matching saved secret; nothing was replaced."
        }
        return $plainValue
    }
    if ($provided) { $plainValue = $provided }
    elseif (-not $AllowCreate) {
        throw "Existing service data has no saved $Name. Supply the original value in the process environment before starting; generating a replacement could make data unreadable."
    } else {
        $randomBytes = New-Object byte[] $Bytes
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($randomBytes) } finally { $rng.Dispose() }
        $plainValue = [BitConverter]::ToString($randomBytes).Replace('-', '').ToLowerInvariant()
    }
    if ($Name -eq 'ENCRYPTION_KEY' -and $plainValue -notmatch '\A[0-9a-fA-F]{64}\z') {
        throw 'ENCRYPTION_KEY must contain 64 hexadecimal characters; correct the environment before retrying.'
    }
    if ($Name -eq 'CHATWOOT_SECRET_KEY_BASE' -and $plainValue -notmatch '\A[a-zA-Z0-9]{64,}\z') {
        throw 'CHATWOOT_SECRET_KEY_BASE must contain at least 64 alphanumeric characters; correct the environment before retrying.'
    }
    if ($Name -match '^CHATWOOT_.*_PASSWORD$' -and ($plainValue.Length -lt 24 -or $plainValue -match '[\r\n]')) {
        throw "$Name must contain at least 24 characters with no line breaks; correct the environment before retrying."
    }
    try {
        $encryptedValue = ConvertTo-SecureString -String $plainValue -AsPlainText -Force | ConvertFrom-SecureString
    } catch {
        throw 'Windows DPAPI could not protect the service secret. Run this launcher in a normal PowerShell session under your Windows account with its profile loaded; no plaintext secret was saved.'
    }
    # CreateNew prevents concurrent launchers from replacing one another's secret.
    $stream = [System.IO.File]::Open($secretPath, [System.IO.FileMode]::CreateNew)
    try {
        $payload = [System.Text.Encoding]::UTF8.GetBytes($encryptedValue)
        $stream.Write($payload, 0, $payload.Length)
    } finally { $stream.Dispose() }
    return $plainValue
}

function Start-FreeLLMAPI([bool]$Background) {
    if (-not $freeReady) { throw 'FreeLLMAPI is not built or Node is missing. Run scripts/setup_freellmapi.ps1, then retry.' }
    $processFile = Join-Path $statePath 'freellmapi-process.json'
    if (Test-Path -LiteralPath $processFile) {
        $record = Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
        $running = Get-Process -Id $record.process_id -ErrorAction SilentlyContinue
        if ($running -and $running.StartTime.ToUniversalTime().ToString('o') -eq $record.started_utc) {
            $instance = Get-CimInstance Win32_Process -Filter "ProcessId=$($running.Id)"
            if ($instance.CommandLine -and $instance.CommandLine.Contains($freeLauncher)) {
                Write-Output "FreeLLMAPI launcher already running (PID $($running.Id)); no duplicate started."
                return
            }
            throw 'Saved PID belongs to an unexpected command. Inspect data/operational-services/freellmapi-process.json; no process was stopped or started.'
        }
    }
    $listener = Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw 'Port 3001 is already occupied. Identify the existing service before retrying; no process was stopped.' }
    $dbExists = Test-Path -LiteralPath (Join-Path $workspaceRoot 'data/freellmapi/freeapi.db')
    $oldValue = $env:ENCRYPTION_KEY
    try {
        $env:ENCRYPTION_KEY = Get-PersistentSecret 'ENCRYPTION_KEY' 32 (-not $dbExists)
        if ($Background) {
            $shellPath = (Get-Process -Id $PID).Path
            $child = Start-Process -FilePath $shellPath -ArgumentList @('-NoProfile', '-File', ('"' + $freeLauncher + '"')) -WindowStyle Hidden -WorkingDirectory $workspaceRoot -RedirectStandardOutput (Join-Path $statePath 'freellmapi.stdout.log') -RedirectStandardError (Join-Path $statePath 'freellmapi.stderr.log') -PassThru
            @{ process_id = $child.Id; started_utc = $child.StartTime.ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
            Start-Sleep -Milliseconds 700
            $child.Refresh()
            if ($child.HasExited) { throw 'FreeLLMAPI launcher exited. Inspect data/operational-services/freellmapi.stderr.log, correct the reported problem, then retry.' }
            Write-Output "FreeLLMAPI launcher started (PID $($child.Id)); health and provider configuration are not yet verified. Open http://127.0.0.1:3001."
        } else {
            & $freeLauncher
        }
    } finally { $env:ENCRYPTION_KEY = $oldValue }
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'This launcher requires Windows DPAPI. Use the existing service launchers with managed environment secrets on other systems.'
    }
    & git -C $workspaceRoot check-ignore --quiet -- 'data/operational-services/probe.dpapi'
    if ($LASTEXITCODE -ne 0) { throw 'Secret directory is not ignored by Git. Add data/operational-services/ to .gitignore before starting.' }
    New-Item -ItemType Directory -Path $statePath -Force | Out-Null
    if ($Service -in @('All', 'FreeLLMAPI')) { Start-FreeLLMAPI ($Service -eq 'All') }
    if ($Service -in @('All', 'Chatwoot')) {
        if (-not $dockerReady) {
            Write-Output 'Chatwoot blocked: install/start Docker Desktop with Linux engine and Compose v2, then rerun -Service Chatwoot.'
            exit 2
        }
        $volumes = & docker volume ls --filter 'label=com.docker.compose.project=kiara-chatwoot' --format '{{.Name}}'
        if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Chatwoot Docker volumes. Start Docker Desktop and retry; no Chatwoot secret was created.' }
        $allowNew = -not [bool]$volumes
        $names = @('CHATWOOT_SECRET_KEY_BASE', 'CHATWOOT_POSTGRES_PASSWORD', 'CHATWOOT_REDIS_PASSWORD')
        $previousValues = @{}
        try {
            foreach ($name in $names) {
                $previousValues[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
                [Environment]::SetEnvironmentVariable($name, (Get-PersistentSecret $name 32 $allowNew), 'Process')
            }
            & $chatLauncher
        } finally {
            foreach ($name in $previousValues.Keys) { [Environment]::SetEnvironmentVariable($name, $previousValues[$name], 'Process') }
        }
    }
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
}
