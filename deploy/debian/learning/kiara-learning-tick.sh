#!/bin/sh
# Kiara learning: asks the Kiara API to learn from the lead searches (lessons per workspace + general
# patterns without personal data), uploads the team's notes (vault folder "Ensinar a Kiara") and writes the
# Obsidian vault with the general patterns. "guides" mode skips the search learning (run after a note sync).
# Secrets come from systemd LoadCredential (KIARA_API_URL, KIARA_WORKER_TOKEN); never printed.
set -eu
env_file="${CREDENTIALS_DIRECTORY:?}/env"
api_url=$(sed -n 's/^KIARA_API_URL=//p' "$env_file")
token=$(sed -n 's/^KIARA_WORKER_TOKEN=//p' "$env_file")
vault="${KIARA_VAULT_DIR:-/var/lib/kiara-vault}"
mode="${1:-tick}"
case "$api_url" in https://*) ;; *) echo "KIARA_API_URL must be https" >&2; exit 1 ;; esac
if [ "$mode" = tick ]; then
  # The summary has only counts (workspaces, lessons, patterns).
  curl -sS -m 280 --proto =https -X POST -H "Authorization: Bearer $token" -H "Content-Length: 0" \
    -w ' http=%{http_code}\n' "$api_url/v1/learning/internal/tick"
fi
notes=$(mktemp)
guides=$(mktemp)
trap 'rm -f "$notes" "$guides"' EXIT
# The team's notes go up as one set (a note deleted in Obsidian stops being used). A failure here never stops
# the vault update. Without the folder nothing is sent, so a missing sync never erases what Kiara learned.
if [ -d "$vault/Ensinar a Kiara" ]; then
  python3 - "$vault" > "$guides" <<'PY'
import json, os, sys
vault = os.path.realpath(sys.argv[1]); base = os.path.join(vault, "Ensinar a Kiara"); files = {}
for folder, dirs, names in os.walk(base):
    dirs[:] = sorted(d for d in dirs if not d.startswith("."))
    for name in sorted(names):
        path = os.path.realpath(os.path.join(folder, name))
        if name.endswith(".md") and path.startswith(base + os.sep) and len(files) < 200:
            with open(path, encoding="utf-8", errors="replace") as handle:
                files[os.path.relpath(path, vault).replace(os.sep, "/")] = handle.read(20000)
json.dump({"files": files}, sys.stdout, ensure_ascii=False)
PY
  curl -sS -m 60 --proto =https -f -X PUT -H "Authorization: Bearer $token" -H "Content-Type: application/json" \
    --data-binary @"$guides" -w ' guides http=%{http_code}\n' "$api_url/v1/learning/internal/guides" || echo "guides: envio falhou" >&2
fi
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
