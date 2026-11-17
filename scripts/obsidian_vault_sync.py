"""Syncs the Kiara vault on Debian with a folder inside the local Obsidian vault.

Only one folder of the local vault takes part (default: "Documents/Kiara Vault/60 - Kiara (servidor)"):

- "Kiara/": written by the Kiara server (patterns, what Kiara read). Copied from Debian; local edits are replaced.
- "Ensinar a Kiara/": notes written here, in Obsidian. Sent to Debian when they change, and the server uploads them
  to the Kiara API, which uses them in every chat. Deleting a note here stops Kiara from using it.
  If this folder is missing locally, it is restored from Debian (a missing folder never erases what Kiara learned).

Nothing else in the local vault leaves this computer. Reaches Debian on the home network (ssh kiara-debian) or
from anywhere through the personal Tailscale (ssh kiara-debian-remoto). Meant for a scheduled task every few
minutes (pythonw, no window); a run that cannot reach Debian just logs and tries again next time.
Only the standard library; usage: python obsidian_vault_sync.py [local folder]
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

REMOTE_VAULT = "/var/lib/private/kiara-vault"
SERVER_DIR, TEAM_DIR = "Kiara", "Ensinar a Kiara"
HOSTS = (("kiara-debian", 5), ("kiara-debian-remoto", 25))
GIT_SSH = Path(r"C:\Program Files\Git\usr\bin\ssh.exe")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
GUIDE = """# Como ensinar a Kiara

Escreva notas nesta pasta (uma por assunto) e a Kiara passa a usar no chat de **todas as empresas**, em poucos minutos.

Bons assuntos: como apresentar a Kiara, tom de voz, o que oferecer em cada nicho, respostas para dúvidas comuns,
o que nunca dizer.

- Não coloque dados de clientes (nomes, telefones, conversas) nem senhas.
- Notas que começam com _ (como esta) são rascunhos: a Kiara ignora.
- Apagar uma nota daqui faz a Kiara parar de usar.
- Veja em [[O que a Kiara leu]] quais notas ela está usando.
"""


def log(root: Path, message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
    target = root / ".sync.log"
    try:
        previous = target.read_text(encoding="utf-8").splitlines(keepends=True)[-200:] if target.exists() else []
        target.write_text("".join(previous) + line, encoding="utf-8")
    except OSError:
        pass
    print(line, end="")


def ssh(host: str, timeout: int, command: str, data: bytes | None = None, wait: int = 120) -> subprocess.CompletedProcess[bytes]:
    binary = str(GIT_SSH) if GIT_SSH.exists() else "ssh"
    return subprocess.run([binary, "-o", "BatchMode=yes", "-o", f"ConnectTimeout={timeout}", host, command],
                          input=data, capture_output=True, timeout=wait, creationflags=NO_WINDOW, check=False)


def pick_host() -> tuple[str, int] | None:
    for host, timeout in HOSTS:
        try:
            if ssh(host, timeout, "true", wait=timeout + 15).returncode == 0:
                return host, timeout
        except subprocess.TimeoutExpired:
            continue
    return None


def notes(folder: Path) -> dict[str, bytes]:
    """Markdown notes under folder (relative path -> bytes); hidden files and folders are skipped."""
    found = {}
    for path in sorted(folder.rglob("*.md")):
        relative = path.relative_to(folder)
        if not any(part.startswith(".") for part in relative.parts) and path.is_file():
            found[relative.as_posix()] = path.read_bytes()
    return found


def fingerprint(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        digest.update(name.encode() + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


def extract(archive: bytes, target: Path, prefix: str) -> int:
    """Replaces target with the .md files under prefix/ in the archive. Returns how many notes."""
    staging = target.with_name(target.name + ".sync-new")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            name = member.name.lstrip("./")
            if not member.isfile() or not name.startswith(prefix + "/") or not name.endswith(".md") or ".." in name.split("/"):
                continue
            destination = staging / name[len(prefix) + 1:]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(tar.extractfile(member).read())
            count += 1
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)
    return count


def pack(prefix: str, files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(f"{prefix}/{name}")
            info.size, info.mode, info.mtime = len(data), 0o644, int(time.time())
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


PUSH = (f"sudo -n sh -c 'set -e; d={REMOTE_VAULT}; n=\"$d/.ensinar-new\"; rm -rf \"$n\"; mkdir -m 0755 \"$n\"; "
        f"tar -xf - -C \"$n\" --no-same-owner --no-same-permissions; chmod -R a+rX,go-w \"$n\"; "
        f"rm -rf \"$d/{TEAM_DIR}\"; mv \"$n/{TEAM_DIR}\" \"$d/{TEAM_DIR}\"; rmdir \"$n\"; "
        f"systemctl start --no-block kiara-learning-guides.service'")


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Documents" / "Kiara Vault" / "60 - Kiara (servidor)"
    root.mkdir(parents=True, exist_ok=True)
    state_file = root / ".sync-state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    chosen = pick_host()
    if not chosen:
        log(root, "Debian fora de alcance; tento de novo na próxima.")
        return 0
    host, timeout = chosen
    team = root / TEAM_DIR
    messages = []

    if not team.is_dir():
        # Restores the team notes from Debian (or starts the folder with the how-to note).
        result = ssh(host, timeout, f"sudo -n tar -C {REMOTE_VAULT} -cf - '{TEAM_DIR}' 2>/dev/null || true")
        count = extract(result.stdout, team, TEAM_DIR) if result.stdout else 0
        if not count:
            team.mkdir(parents=True, exist_ok=True)
        messages.append(f"{TEAM_DIR}: {count} notas trazidas do servidor")
        state["team"] = fingerprint(notes(team)) if count else ""
    if not (team / "_Como ensinar a Kiara.md").exists():
        (team / "_Como ensinar a Kiara.md").write_text(GUIDE, encoding="utf-8")

    local = notes(team)
    current = fingerprint(local)
    if current != state.get("team"):
        result = ssh(host, timeout, PUSH, data=pack(TEAM_DIR, local))
        if result.returncode != 0:
            log(root, f"envio falhou ({result.returncode}): {result.stderr.decode(errors='replace').strip()[:200]}")
            return 1
        state["team"] = current
        messages.append(f"{TEAM_DIR}: {len(local)} notas enviadas")

    result = ssh(host, timeout, f"sudo -n tar -C {REMOTE_VAULT} -cf - {SERVER_DIR}")
    if result.returncode != 0 or not result.stdout:
        log(root, f"leitura falhou ({result.returncode}): {result.stderr.decode(errors='replace').strip()[:200]}")
        return 1
    count = extract(result.stdout, root / SERVER_DIR, SERVER_DIR)
    messages.append(f"{SERVER_DIR}: {count} notas")
    state_file.write_text(json.dumps(state), encoding="utf-8")
    log(root, f"ok via {host}: " + "; ".join(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
