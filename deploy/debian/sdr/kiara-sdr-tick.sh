#!/bin/sh
# Kiara SDR heartbeat: asks the Kiara API to sync WhatsApp, understand conversations, draft/send replies and
# follow-ups. All logic and anti-ban rules live in the API; this only knocks on the door.
# Secrets come from systemd LoadCredential (KIARA_API_URL, KIARA_WORKER_TOKEN); never printed.
set -eu
env_file="${CREDENTIALS_DIRECTORY:?}/env"
api_url=$(sed -n 's/^KIARA_API_URL=//p' "$env_file")
token=$(sed -n 's/^KIARA_WORKER_TOKEN=//p' "$env_file")
case "$api_url" in https://*) ;; *) echo "KIARA_API_URL must be https" >&2; exit 1 ;; esac
# The summary has only counts (synced, analyzed, drafted, sent...), no message text.
curl -sS -m 280 --proto =https -X POST -H "Authorization: Bearer $token" -H "Content-Length: 0" \
  -w ' http=%{http_code}\n' "$api_url/v1/sdr/internal/tick"
