param(
  [string]$Background = (Join-Path $PSScriptRoot '..\example\assets\gym-clean-plate-v1.png'),
  [string]$Person = (Join-Path $PSScriptRoot '..\example\assets\professional-cutout-alpha-v1.png'),
  [string]$Output = (Join-Path $PSScriptRoot '..\media-source\hero-demo-source.mp4'),
  [switch]$Force
)

. (Join-Path $PSScriptRoot 'ffmpeg-tools.ps1')
$Background = [IO.Path]::GetFullPath($Background)
$Person = [IO.Path]::GetFullPath($Person)
$Output = [IO.Path]::GetFullPath($Output)

if (-not (Test-Path -LiteralPath $Background)) { throw "Fundo nao encontrado: $Background" }
if (-not (Test-Path -LiteralPath $Person)) { throw "Pessoa nao encontrada: $Person" }
if ((Test-Path -LiteralPath $Output) -and -not $Force) { throw "Saida ja existe: $Output. Use -Force para substituir." }

New-Item -ItemType Directory -Path (Split-Path -Parent $Output) -Force | Out-Null
$filter = "[0:v]scale=1120:1410,crop=1080:1350:x='20+10*sin(t*0.4)':y='30+8*cos(t*0.35)'[bg];[1:v]scale=1080:1350,format=rgba[person];[bg][person]overlay=x='-220+220*min(t/1.35,1)+7*sin(t*1.7)':y='-5+3*sin(t*1.25)':format=auto[out]"

$arguments = @(
  '-y', '-loop', '1', '-framerate', '30', '-t', '4', '-i', $Background,
  '-loop', '1', '-framerate', '30', '-t', '4', '-i', $Person,
  '-filter_complex', $filter, '-map', '[out]',
  '-t', '4', '-an', '-r', '30', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
  '-movflags', '+faststart', $Output
)
Invoke-FFmpeg -Arguments $arguments
Write-Host "Cena-fonte criada: $Output"
