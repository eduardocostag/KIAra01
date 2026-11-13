param(
  [Parameter(Mandatory)][string]$Image,
  [string]$SceneId = ('hero-' + (Get-Date -Format 'yyyyMMdd-HHmmss')),
  [ValidateSet('Entrada premium','Impacto 3D','Respiração cinematográfica')]
  [string]$Preset = 'Entrada premium',
  [ValidateRange(2,5)][double]$Duration = 3,
  [ValidateSet('real','light')][string]$Engine = 'real',
  [string]$Prompt = 'A fit male personal trainer in a black shirt comes alive naturally. He shifts his torso, looks confidently toward the camera, then extends his right arm forward and slightly to the right as if reaching for and grabbing a glowing interface button. Realistic body motion, fixed camera, cinematic gym lighting, preserve his identity, face and clothing.',
  [ValidateRange(6,30)][int]$FrameRate = 12,
  [ValidateRange(24,240)][int]$MaxFrames = 96,
  [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$imagePath = [IO.Path]::GetFullPath($Image)
$packagesRoot = Join-Path $projectRoot '.tools\hf-client'
$generatedRoot = Join-Path $projectRoot 'media-source\generated'
$sourceVideo = Join-Path $generatedRoot "$SceneId-source.mp4"
$clientScript = Join-Path $PSScriptRoot 'request-cinematic-clip.py'
$buildScript = Join-Path $PSScriptRoot 'build-cinematic-assets.ps1'

if (-not (Test-Path -LiteralPath $imagePath -PathType Leaf)) {
  throw "Imagem não encontrada: $imagePath"
}

New-Item -ItemType Directory -Force -Path $packagesRoot, $generatedRoot | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $packagesRoot 'gradio_client'))) {
  Write-Host 'Instalando cliente da API no diretório isolado do projeto...'
  & python -m pip install --disable-pip-version-check --no-deps --target $packagesRoot 'gradio_client==1.12.1' 'websockets==15.0.1'
  if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar o cliente Gradio.' }
}

$previousPythonPath = $env:PYTHONPATH
$previousHfHome = $env:HF_HOME
try {
  $env:PYTHONPATH = $packagesRoot
  $env:HF_HOME = Join-Path $projectRoot '.hf-home'
  Write-Host "Solicitando clipe ao ZeroGPU: $SceneId"
  & python $clientScript --image $imagePath --output $sourceVideo --preset $Preset --duration $Duration --engine $Engine --prompt $Prompt
  if ($LASTEXITCODE -ne 0) { throw 'O gerador remoto não retornou o clipe.' }
}
finally {
  $env:PYTHONPATH = $previousPythonPath
  $env:HF_HOME = $previousHfHome
}

$buildArgs = @{
  InputVideo = $sourceVideo
  SceneId = $SceneId
  FrameRate = $FrameRate
  MaxFrames = $MaxFrames
}
if ($Force) { $buildArgs.Force = $true }

& $buildScript @buildArgs
if ($LASTEXITCODE -ne 0) { throw 'Falha ao montar os assets cinematográficos.' }

Write-Host "Cena pronta: example\assets\cinema\$SceneId"
