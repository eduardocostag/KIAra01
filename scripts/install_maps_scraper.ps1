param([string]$Destination = "")
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$workspace = Split-Path -Parent $PSScriptRoot
if (-not $Destination) {
    $Destination = Join-Path $workspace 'data/tools/google-maps-scraper'
}
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
$workspacePath = [System.IO.Path]::GetFullPath($workspace).TrimEnd('\') + '\'
if (-not $destinationPath.StartsWith($workspacePath, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'O destino precisa estar dentro do workspace Kiara.'
}
$version = '1.18.2'
$expectedHash = '6609e9638ee303b6d419a329f629efcd9ed5d083f86ad6b93f92a21d59c2aca5'
$url = "https://github.com/gosom/google-maps-scraper/releases/download/v$version/google_maps_scraper-$version-windows-amd64.exe"
New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
$target = Join-Path $destinationPath 'google-maps-scraper.exe'
if (Test-Path -LiteralPath $target) {
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
        throw 'O executável existente difere da release esperada; preserve-o e escolha outro destino.'
    }
} else {
    $downloadPath = Join-Path $destinationPath ('download-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $pythonPath = Join-Path $workspace '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $pythonPath) {
        & $pythonPath -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' $url $downloadPath
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao baixar Google Maps Scraper.' }
    } else {
        Invoke-WebRequest -Uri $url -OutFile $downloadPath
    }
    if ((Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
        Remove-Item -LiteralPath $downloadPath
        throw 'Checksum do Google Maps Scraper inválido.'
    }
    Move-Item -LiteralPath $downloadPath -Destination $target
}
Write-Output "Google Maps Scraper v$version instalado e SHA-256 verificado: $target"
Write-Output 'Configure KIARA_MAPS_SCRAPER_EXECUTABLE com esse caminho antes de iniciar a Kiara.'
