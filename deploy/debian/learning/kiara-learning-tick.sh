#!/bin/sh
# Kiara learning: asks the Kiara API to learn from the lead searches (lessons per workspace + general
# patterns without personal data) and writes the Obsidian vault with the general patterns.
# Secrets come from systemd LoadCredential (KIARA_API_URL, KIARA_WORKER_TOKEN); never printed.
set -eu
env_file="${CREDENTIALS_DIRECTORY:?}/env"
api_url=$(sed -n 's/^KIARA_API_URL=//p' "$env_file")
token=$(sed -n 's/^KIARA_WORKER_TOKEN=//p' "$env_file")
vault="${KIARA_VAULT_DIR:-/var/lib/kiara-vault}"
case "$api_url" in https://*) ;; *) echo "KIARA_API_URL must be https" >&2; exit 1 ;; esac
# The summary has only counts (workspaces, lessons, patterns).
curl -sS -m 280 --proto =https -X POST -H "Authorization: Bearer $token" -H "Content-Length: 0" \
  -w ' http=%{http_code}\n' "$api_url/v1/learning/internal/tick"
notes=$(mktemp)
trap 'rm -f "$notes"' EXIT
curl -sS -m 60 --proto =https -f -H "Authorization: Bearer $token" "$api_url/v1/learning/internal/vault" -o "$notes"
# Writes each note atomically inside the vault; paths are checked so nothing escapes the folder.
python3 - "$notes" "$vault" <<'PY'
import json, os, sys, tempfile
notes, vault = json.load(open(sys.argv[1], encoding="utf-8"))["files"], os.path.realpath(sys.argv[2])
os.makedirs(os.path.join(vault, ".obsidian"), exist_ok=True)
for relative, text in notes.items():
    target = os.path.realpath(os.path.join(vault, relative))
    if not target.startswith(vault + os.sep) or not target.endswith(".md"):
        continue
    os.makedirs(os.path.dirname(target), exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=os.path.dirname(target), suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(text)
    os.chmod(temporary, 0o644)
    os.replace(temporary, target)
print(f"vault: {len(notes)} notas")
PY
