Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-FFmpegTool {
  param([Parameter(Mandatory)][string]$Name)

  $command = Get-Command $Name -ErrorAction SilentlyContinue
  if ($command) { return $command.Source }

  $packageRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe'
  $candidate = Get-ChildItem -LiteralPath $packageRoot -Recurse -Filter "$Name.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($candidate) { return $candidate.FullName }

  throw "$Name nao foi encontrado. Reinicie o terminal ou instale Gyan.FFmpeg pelo winget."
}

function Invoke-FFmpeg {
  param([Parameter(Mandatory)][string[]]$Arguments)
  $binary = Find-FFmpegTool -Name 'ffmpeg'
  & $binary @Arguments
  if ($LASTEXITCODE -ne 0) { throw "FFmpeg encerrou com codigo $LASTEXITCODE." }
}

function Invoke-FFprobeJson {
  param([Parameter(Mandatory)][string]$InputPath)
  $binary = Find-FFmpegTool -Name 'ffprobe'
  $json = & $binary '-v' 'error' '-show_entries' 'format=duration:stream=width,height,r_frame_rate' '-of' 'json' $InputPath
  if ($LASTEXITCODE -ne 0) { throw "FFprobe encerrou com codigo $LASTEXITCODE." }
  return ($json | ConvertFrom-Json)
}
