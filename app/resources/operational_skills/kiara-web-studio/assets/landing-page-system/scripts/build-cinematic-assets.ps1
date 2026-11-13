param(
  [Parameter(Mandatory)][string]$InputVideo,
  [string]$SceneId = 'hero-v1',
  [string]$OutputRoot = (Join-Path $PSScriptRoot '..\example\assets\cinema'),
  [ValidateRange(6,30)][int]$FrameRate = 12,
  [ValidateRange(24,240)][int]$MaxFrames = 96,
  [switch]$Force
)

. (Join-Path $PSScriptRoot 'ffmpeg-tools.ps1')
$InputVideo = [IO.Path]::GetFullPath($InputVideo)
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
$sceneRoot = Join-Path $OutputRoot $SceneId
$framesRoot = Join-Path $sceneRoot 'frames'

if (-not (Test-Path -LiteralPath $InputVideo)) { throw "Video nao encontrado: $InputVideo" }
if ((Test-Path -LiteralPath $sceneRoot) -and -not $Force) { throw "Cena ja existe: $sceneRoot. Use outro SceneId ou -Force." }

New-Item -ItemType Directory -Path $framesRoot -Force | Out-Null
$probe = Invoke-FFprobeJson -InputPath $InputVideo
$duration = [math]::Round([double]$probe.format.duration, 3)

Invoke-FFmpeg -Arguments @('-y','-i',$InputVideo,'-vf','scale=960:-2:force_original_aspect_ratio=decrease','-frames:v','1','-c:v','libwebp','-quality','82',(Join-Path $sceneRoot 'poster.webp'))
Invoke-FFmpeg -Arguments @('-y','-i',$InputVideo,'-an','-vf','scale=1440:-2:force_original_aspect_ratio=decrease','-c:v','libvpx-vp9','-crf','31','-b:v','0','-row-mt','1',(Join-Path $sceneRoot 'desktop.webm'))
Invoke-FFmpeg -Arguments @('-y','-i',$InputVideo,'-an','-vf','scale=720:-2:force_original_aspect_ratio=decrease','-c:v','libx264','-preset','medium','-crf','24','-pix_fmt','yuv420p','-movflags','+faststart',(Join-Path $sceneRoot 'mobile.mp4'))
Invoke-FFmpeg -Arguments @('-y','-i',$InputVideo,'-vf',"fps=$FrameRate,scale=1080:-2:force_original_aspect_ratio=decrease",'-frames:v',"$MaxFrames",'-c:v','libwebp','-quality','78',(Join-Path $framesRoot 'frame-%03d.webp'))

$frames = @(Get-ChildItem -LiteralPath $framesRoot -Filter 'frame-*.webp').Count
$manifest = [ordered]@{
  schemaVersion = 1
  id = $SceneId
  generatedAt = (Get-Date).ToUniversalTime().ToString('o')
  duration = $duration
  poster = "assets/cinema/$SceneId/poster.webp"
  desktop = [ordered]@{ type='sequence'; template="assets/cinema/$SceneId/frames/frame-{frame}.webp"; frames=$frames; fps=$FrameRate; pad=3 }
  mobile = [ordered]@{ type='video'; src="assets/cinema/$SceneId/mobile.mp4"; duration=$duration }
  fallback = [ordered]@{ type='poster'; src="assets/cinema/$SceneId/poster.webp" }
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $sceneRoot 'manifest.json') -Encoding utf8

Write-Host "Pacote criado: $sceneRoot"
Write-Host "Duracao: $duration s | Frames: $frames | FPS: $FrameRate"
