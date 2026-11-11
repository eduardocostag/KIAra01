param(
    [ValidateSet('Start', 'Status', 'Stop')][string]$Action = 'Start',
    [ValidateRange(1024, 65535)][int]$Port = 3006,
    [switch]$Background,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$servicePath = Join-Path $workspaceRoot 'services/openwa'
$statePath = Join-Path $workspaceRoot 'data/openwa'
$entryPath = Join-Path $servicePath 'dist/main.js'
$preloadPath = Join-Path $workspaceRoot 'infra/openwa/loopback.cjs'
$processFile = Join-Path $statePath 'process.json'
$chromePath = Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe'
if (-not (Test-Path -LiteralPath $chromePath)) {
    $chromePath = Join-Path ${env:ProgramFiles(x86)} 'Google/Chrome/Application/chrome.exe'
}
if ($CheckOnly) {
    Write-Output "Node available: $([bool](Get-Command node -ErrorAction SilentlyContinue))"
    Write-Output "Server built: $(Test-Path -LiteralPath $entryPath)"
    Write-Output "Dashboard built: $(Test-Path -LiteralPath (Join-Path $servicePath 'dashboard/dist/index.html'))"
    Write-Output "Chrome available: $(Test-Path -LiteralPath $chromePath)"
    Write-Output "Local URL: http://127.0.0.1:$Port"
    Write-Output 'No key was read or created; no process or WhatsApp session was started.'
    exit 0
}

function Get-OwnedProcess {
    if (-not (Test-Path -LiteralPath $processFile)) { return $null }
    $record = Get-Content -LiteralPath $processFile -Raw | ConvertFrom-Json
    $running = Get-Process -Id $record.process_id -ErrorAction SilentlyContinue
    if (-not $running -or $running.StartTime.ToUniversalTime().ToString('o') -ne $record.started_utc) { return $null }
    $instance = Get-CimInstance Win32_Process -Filter "ProcessId=$($running.Id)"
    if (-not $instance.CommandLine -or -not $instance.CommandLine.Contains($entryPath) -or -not $instance.CommandLine.Contains($preloadPath)) {
        throw 'Saved OpenWA PID does not match this launcher; no process was stopped or started.'
    }
    return $running
}

function Get-LocalSecret([string]$Name) {
    $path = Join-Path $statePath "$Name.dpapi"
    $provided = [Environment]::GetEnvironmentVariable("OPENWA_$Name", 'Process')
    if (Test-Path -LiteralPath $path) {
        try {
            $secureValue = Get-Content -LiteralPath $path -Raw | ConvertTo-SecureString
            $value = [System.Net.NetworkCredential]::new('', $secureValue).Password
        } catch { throw "Cannot decrypt OpenWA $Name; the existing key was not replaced." }
        if ($provided -and $provided -cne $value) { throw "OPENWA_$Name differs from the saved key; no value was replaced." }
        return $value
    }
    if ($provided) { $value = $provided }
    else {
        if (Test-Path -LiteralPath (Join-Path $statePath 'main.sqlite')) {
            throw "Existing OpenWA database has no saved $Name; provide its original OPENWA_$Name before retrying."
        }
        $bytes = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $value = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    }
    if ($value.Length -lt 32 -or $value -match '[\r\n]') { throw "OPENWA_$Name needs at least 32 characters without line breaks." }
    try {
        $encrypted = ConvertTo-SecureString -String $value -AsPlainText -Force | ConvertFrom-SecureString
    } catch { throw 'Windows DPAPI could not protect the OpenWA key. Run under the same Windows user with its profile loaded; no plaintext key was written.' }
    $stream = [System.IO.File]::Open($path, [System.IO.FileMode]::CreateNew)
    try { $payload = [System.Text.Encoding]::UTF8.GetBytes($encrypted); $stream.Write($payload, 0, $payload.Length) }
    finally { $stream.Dispose() }
    return $value
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'This launcher requires Windows DPAPI.' }
if ($Action -eq 'Status' -or $Action -eq 'Stop') {
    $running = Get-OwnedProcess
    if (-not $running) { Write-Output 'No OpenWA process owned by this launcher is running.'; exit 0 }
    if ($Action -eq 'Stop') {
        # Stop only the verified local process; persisted sessions and SQLite files stay intact.
        Stop-Process -Id $running.Id
        Write-Output 'OpenWA stopped; local databases and sessions were preserved.'
    } else { Write-Output "OpenWA process running (PID $($running.Id)); URL http://127.0.0.1:$Port. Health and account connection are separate checks." }
    exit 0
}
Get-Command node -ErrorAction Stop | Out-Null
foreach ($file in @($entryPath, $preloadPath, (Join-Path $servicePath 'dashboard/dist/index.html'), $chromePath)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'OpenWA build or Chrome missing. Run scripts/setup_openwa.ps1 and install Chrome before starting.' }
}
& git -C $workspaceRoot check-ignore --quiet -- 'data/openwa/probe.dpapi'
if ($LASTEXITCODE -ne 0) { throw 'data/openwa/ must be ignored by Git before keys are created.' }
$running = Get-OwnedProcess
if ($running) { Write-Output "OpenWA already running (PID $($running.Id)); no duplicate started."; exit 0 }
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is occupied; no existing process was changed." }
New-Item -ItemType Directory -Force -Path $statePath | Out-Null
$settings = @{
    NODE_ENV = 'production'; PORT = "$Port"; BASE_URL = "http://127.0.0.1:$Port";
    DASHBOARD_URL = "http://127.0.0.1:$Port"; CORS_ORIGINS = "http://127.0.0.1:$Port,http://localhost:$Port";
    DATABASE_TYPE = 'sqlite'; DATABASE_NAME = (Join-Path $statePath 'openwa.sqlite');
    MAIN_DATABASE_NAME = (Join-Path $statePath 'main.sqlite'); DATABASE_SYNCHRONIZE = 'false';
    MAIN_DATABASE_SYNCHRONIZE = 'false'; DATABASE_LOGGING = 'false';
    POSTGRES_BUILTIN = 'false'; REDIS_ENABLED = 'false'; REDIS_BUILTIN = 'false'; QUEUE_ENABLED = 'false';
    STORAGE_TYPE = 'local'; STORAGE_LOCAL_PATH = (Join-Path $statePath 'media'); MINIO_BUILTIN = 'false';
    SESSION_DATA_PATH = (Join-Path $statePath 'sessions'); BAILEYS_AUTH_DIR = (Join-Path $statePath 'baileys');
    PLUGIN_STATE_DIR = (Join-Path $statePath 'plugin-state'); PLUGINS_DIR = (Join-Path $statePath 'plugins');
    ENGINE_TYPE = 'whatsapp-web.js'; PUPPETEER_EXECUTABLE_PATH = $chromePath; PUPPETEER_HEADLESS = 'true';
    AUTO_START_SESSIONS = 'true'; MAX_CONCURRENT_SESSIONS = '1'; SEND_PACING_ENABLED = 'true';
    SEND_PACING_WARMUP_SCHEDULE = '20,20,20,20,20,20,20'; SEND_PACING_COLD_DAILY_CAP = '5,5,5,5,5,5,5';
    LOG_LEVEL = 'warn'; LOG_FORMAT = 'json'; ENABLE_SWAGGER = 'false'; MCP_ENABLED = 'false';
    # The upstream convenience file is not needed: DPAPI holds the bootstrap key.
    BOOTSTRAP_KEY_FILE = 'NUL'; ALLOW_DEV_API_KEY = 'false';
}
$settings.API_MASTER_KEY = Get-LocalSecret 'API_MASTER_KEY'
$settings.API_KEY_PEPPER = Get-LocalSecret 'API_KEY_PEPPER'
$previous = @{}
foreach ($name in $settings.Keys) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    foreach ($name in $settings.Keys) { [Environment]::SetEnvironmentVariable($name, $settings[$name], 'Process') }
    $nodePath = (Get-Command node).Source
    $arguments = @('--require', ('"' + $preloadPath + '"'), ('"' + $entryPath + '"'))
    if ($Background) {
        $child = Start-Process -FilePath $nodePath -ArgumentList $arguments -WorkingDirectory $statePath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $statePath 'stdout.log') -RedirectStandardError (Join-Path $statePath 'stderr.log') -PassThru
        @{ process_id = $child.Id; started_utc = $child.StartTime.ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
        Start-Sleep -Milliseconds 700
        $child.Refresh()
        if ($child.HasExited) { throw 'OpenWA exited during startup; inspect data/openwa/stderr.log locally.' }
        Write-Output "OpenWA started (PID $($child.Id)); inspect http://127.0.0.1:$Port. No WhatsApp session was created by this launcher."
    } else {
        Push-Location -LiteralPath $statePath
        try { & $nodePath --require $preloadPath $entryPath; if ($LASTEXITCODE -ne 0) { throw "OpenWA exited with code $LASTEXITCODE." } }
        finally { Pop-Location }
    }
} finally {
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
}
