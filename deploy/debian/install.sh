#!/usr/bin/env bash
# Kiara on an always-on Debian machine: chat bridge (voice, transcription, videos),
# OmniRoute and a public HTTPS address through Tailscale Funnel. No ports are opened on the router.
#
# Usage, from the cloned repository on the Debian machine:
#   sudo bash deploy/debian/install.sh
# Safe to run again: it updates dependencies and restarts the services.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Execute com sudo: sudo bash deploy/debian/install.sh" >&2; exit 1; fi
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVICE_USER="kiara"
SERVICE_HOME="/var/lib/kiara"
BROWSERS="/opt/kiara/ms-playwright"
OMNIROUTE_VERSION="3.8.51"
case "$REPO" in /home/*|/root/*)
  echo "Coloque o repositório fora de /home (o serviço roda isolado da pasta pessoal), por exemplo:" >&2
  echo "  sudo mv \"$REPO\" /opt/kiara/KIAra01 && cd /opt/kiara/KIAra01" >&2; exit 1;;
esac
step() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

step "Pacotes do sistema"
apt-get update -q
apt-get install -y -q ca-certificates curl git ffmpeg fonts-noto-core fonts-noto-color-emoji build-essential

step "Node.js 22 (OmniRoute)"
if ! command -v node >/dev/null || (( $(node -p 'process.versions.node.split(".")[0]') < 20 )); then
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor --yes -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list
  apt-get update -q && apt-get install -y -q nodejs
fi
npm install -g --no-fund --no-audit "omniroute@${OMNIROUTE_VERSION}"

step "Servidor sempre ligado (sem suspensão)"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null

step "Usuário de serviço '${SERVICE_USER}'"
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$SERVICE_HOME" --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$REPO/data" "$REPO/.cache"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0755 "$BROWSERS"
chown -R "$SERVICE_USER:$SERVICE_USER" "$REPO"

step "Python 3.12 e dependências da Kiara (uv)"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh
fi
as_kiara() { sudo -u "$SERVICE_USER" -H env HOME="$SERVICE_HOME" PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" UV_PYTHON_INSTALL_DIR="$SERVICE_HOME/python" "$@"; }
cd "$REPO"
as_kiara uv venv --python 3.12 --allow-existing .venv
as_kiara uv pip install --python .venv/bin/python -e . "edge-tts>=7.2,<8" "faster-whisper>=1.1" "numpy>=2.1" "playwright>=1.49" "imageio-ffmpeg==0.6.0" "tzdata>=2024.1"

step "Chromium para os vídeos"
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$REPO/.venv/bin/python" -m playwright install-deps chromium
as_kiara .venv/bin/python -m playwright install chromium

step "Configuração (.env.local)"
if [[ -f "$REPO/.env.local" ]]; then
  chown "$SERVICE_USER:$SERVICE_USER" "$REPO/.env.local"; chmod 0600 "$REPO/.env.local"
  as_kiara .venv/bin/python scripts/run_kiara_chat.py --check-only || echo "!! Revise o .env.local (nenhuma chave foi exibida)."
else
  echo "!! Falta $REPO/.env.local. Copie o arquivo do seu computador (veja o README) e rode este script de novo."
fi

step "Serviços (iniciam com a máquina e reiniciam sozinhos)"
for unit in kiara-chat kiara-omniroute; do
  sed -e "s#@REPO@#$REPO#g" -e "s#@USER@#$SERVICE_USER#g" -e "s#@HOME@#$SERVICE_HOME#g" -e "s#@BROWSERS@#$BROWSERS#g" \
    "$REPO/deploy/debian/$unit.service" > "/etc/systemd/system/$unit.service"
done
systemctl daemon-reload
systemctl enable --now kiara-omniroute.service
if [[ -f "$REPO/.env.local" ]]; then systemctl enable kiara-chat.service && systemctl restart kiara-chat.service; fi

step "Endereço público com HTTPS (Tailscale Funnel)"
if ! command -v tailscale >/dev/null; then curl -fsSL https://tailscale.com/install.sh | sh; fi
if ! tailscale status >/dev/null 2>&1; then
  echo "Abra o link abaixo e entre com sua conta (Google, Microsoft ou GitHub):"
  tailscale up --ssh
fi
tailscale funnel --bg 3008 || echo "!! Ative o Funnel no link mostrado acima e rode: sudo tailscale funnel --bg 3008"
ADDRESS="https://$(tailscale status --json | "$REPO/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"

step "Pronto"
systemctl --no-pager --lines=0 status kiara-chat kiara-omniroute || true
cat <<EOF

Endereço da Kiara: $ADDRESS
Na Vercel, defina NEXT_PUBLIC_KIARA_CHAT_URL=$ADDRESS e publique o site de novo.
Teste: curl -s -o /dev/null -w '%{http_code}\n' -X OPTIONS -H 'Origin: https://kiaralead.vercel.app' $ADDRESS/api/status  (esperado: 204)
EOF
