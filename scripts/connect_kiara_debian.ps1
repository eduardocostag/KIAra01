param([switch]$InstallKey, [switch]$Audit)

$ErrorActionPreference = 'Stop'
$kiaraSshConfig = Join-Path $env:USERPROFILE '.ssh\config'
$kiaraPublicKey = Join-Path $env:USERPROFILE '.ssh\kiara_debian_ed25519.pub'
if (!(Test-Path -LiteralPath $kiaraSshConfig)) { throw 'Alias SSH da Kiara não encontrado no perfil deste usuário.' }
$kiaraSshArgs = @('-F', $kiaraSshConfig, '-o', 'ConnectTimeout=8')

function ConvertTo-KiaraRemoteCommand([string]$Command) {
    # Avoid Windows native-argument quoting changing the remote shell script.
    $kiaraEncodedCommand = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Command))
    return "printf $kiaraEncodedCommand | base64 -d | sh"
}

if ($InstallKey) {
    # Run this switch in the user's own interactive terminal. SSH handles the
    # password prompt; this script never receives or records the password.
    $kiaraKeyText = (Get-Content -LiteralPath $kiaraPublicKey -Raw).Trim()
    if ($kiaraKeyText -notmatch '^ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]*)?$') { throw 'Chave pública inválida.' }
    $kiaraEncodedPublicKey = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($kiaraKeyText))
    $kiaraInstallCommand = 'umask 077; mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh" && touch "$HOME/.ssh/authorized_keys" && key=$(printf KEY_BASE64 | base64 -d) && { grep -qxF -- "$key" "$HOME/.ssh/authorized_keys" || printf "%s\n" "$key" >> "$HOME/.ssh/authorized_keys"; } && chmod 600 "$HOME/.ssh/authorized_keys"'
    $kiaraInstallCommand = $kiaraInstallCommand.Replace('KEY_BASE64', $kiaraEncodedPublicKey)
    & ssh @kiaraSshArgs 'kiara-debian' (ConvertTo-KiaraRemoteCommand $kiaraInstallCommand)
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível autorizar a chave. Nenhum serviço ou firewall foi alterado.' }
}

$kiaraReadOnlyCommand = 'id -un; hostname; uname -s'
if ($Audit) {
    $kiaraReadOnlyCommand = @'
set -eu
printf "== Identity ==\n"
id -un
hostname
grep '^PRETTY_NAME=' /etc/os-release
printf "== Capacity ==\n"
free -h
df -h / /opt/kiara
printf "== Containers ==\n"
sudo -n docker ps --format '{{.Names}} | {{.Image}} | {{.Status}} | {{.Ports}}'
printf "== Loopback health (no credentials) ==\n"
for endpoint in http://127.0.0.1:20128/healthz http://127.0.0.1:2785/api/health; do
  curl --silent --show-error --max-time 8 --output /dev/null --write-out '%{http_code}\n' "$endpoint"
done
printf "== Installed Ollama model ==\n"
sudo -n docker exec kiara-ollama ollama list
'@
}
& ssh @kiaraSshArgs '-o' 'BatchMode=yes' 'kiara-debian' (ConvertTo-KiaraRemoteCommand $kiaraReadOnlyCommand)
if ($LASTEXITCODE -ne 0) { throw 'Acesso não confirmado. Conclua a autenticação ou verifique o sudo autorizado antes da auditoria.' }
