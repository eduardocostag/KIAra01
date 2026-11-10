"""Run Kiara locally against the visible WhatsApp Web interface."""
from __future__ import annotations

# ruff: noqa: BLE001 -- the process boundary must redact arbitrary adapter exception bodies
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if sys.stdout is None or sys.stderr is None:
    log_path = ROOT / "data" / "whatsapp-web" / "executor.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream = log_path.open("a", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream

from app.whatsapp.bridge import SiteBridge
from app.whatsapp.browser import ChromeExtensionBrowser, WhatsAppBrowser
from app.whatsapp.engine import Engine
from app.whatsapp.store import DEFAULT_CONFIG, Store, normalize_phone


class InstanceLock:
    """OS-held lock is released on process death; stale files cannot block restart."""
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.file = open(path, "a+b")  # noqa: SIM115 -- lifetime is held by InstanceLock.close
        self.file.seek(0)
        if not self.file.read(1):
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError("Já existe um executor usando estes dados/perfil.") from None

    def close(self):
        self.file.close()


async def run(args):
    directory = Path(args.data_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    lock = InstanceLock(directory / "executor.lock")
    store = Store(directory / "history.sqlite3")
    extension_bridge = None
    if args.chrome_extension:
        from app.whatsapp.chrome_extension import ChromeExtensionBridge
        extension_bridge = ChromeExtensionBridge()
        extension_bridge.start()
        browser = ChromeExtensionBrowser(extension_bridge)
    else:
        browser = WhatsAppBrowser(directory / "browser-profile")
    try:
        if args.init_config:
            path = Path(args.init_config)
            with path.open("x", encoding="utf-8") as handle:  # noqa: ASYNC230 -- one startup config
                json.dump(DEFAULT_CONFIG, handle, ensure_ascii=False, indent=2)
            print(f"Configuração desativada criada em {path}. Cadastre somente contatos autorizados.")
            return
        if args.config:
            store.configure(json.loads(Path(args.config).read_text(encoding="utf-8")))
        if args.resume:
            store.resume(normalize_phone(args.resume))
            print("Pausa humana removida; contatos com opt-out permanecem bloqueados.")
            return
        if args.pause:
            config = store.config()
            config["enabled"] = False
            store.configure(config)
            print("Automação local pausada. Se conectado ao site, pause também no painel antes de reiniciar.")
            return
        if args.status:
            print(json.dumps({"enabled": store.config()["enabled"], "contacts": len(store.config()["contacts"]),
                              "pending_events": len(store.pending_events()),
                              "outbox": [dict(r) for r in store.db.execute("SELECT status,COUNT(*) AS count FROM outbox GROUP BY status")]}, ensure_ascii=False, indent=2))
            return
        token_provider = None
        if args.site_login:
            from app.whatsapp.site_auth import interactive_site_session
            session = interactive_site_session()
            token_provider = session.token
        bridge = SiteBridge(args.api_url, token_provider)
        if args.site_login and not bridge.configured:
            raise ValueError("Defina KIARA_API_URL ou --api-url para conectar o painel.")
        engine = Engine(store, browser, bridge, max_daily=args.max_daily)
        if not args.chrome_extension:
            await browser.start()
            print("WhatsApp Web aberto. Leia o QR Code manualmente. Ctrl+C encerra o executor.")
        else:
            print("Aguardando comandos da extensão Kiara no Chrome já conectado ao WhatsApp Web.")
        print("Somente contatos habilitados são atendidos. Histórico anterior é ignorado no primeiro acesso.")
        while True:
            try:
                await engine.cycle()
                if engine.last_error:
                    print(engine.last_error)
                    engine.last_error = None
            except Exception as exc:
                # Never log messages, tokens, URLs with credentials, or exception bodies.
                print(f"Ciclo interrompido ({type(exc).__name__}); nenhum envio será repetido automaticamente.")
            if args.once:
                break
            await asyncio.sleep(args.interval)
    finally:
        await browser.close()
        if extension_bridge:
            extension_bridge.close()
        store.close()
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data" / "whatsapp-web"))
    parser.add_argument("--config", help="Arquivo JSON de configuração local (site prevalece quando conectado)")
    parser.add_argument("--init-config", help="Criar exemplo JSON desativado e sair")
    parser.add_argument("--api-url", help="API Kiara para configuração e histórico; também KIARA_API_URL")
    parser.add_argument("--site-login", action="store_true", help="Autenticar no site com e-mail/senha")
    parser.add_argument("--chrome-extension", action="store_true", help="Usar a extensão instalada no Chrome já conectado")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--pause", action="store_true")
    parser.add_argument("--resume", metavar="PHONE", help="Liberar pausa humana local; não remove opt-out")
    parser.add_argument("--once", action="store_true", help="Um ciclo (pode enviar se configuração habilitada)")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--max-daily", type=int, default=500)
    args = parser.parse_args()
    if args.interval < 10 or not 1 <= args.max_daily <= 500:
        parser.error("interval mínimo 10 segundos; max-daily entre 1 e 500")
    # Playwright on Windows requires subprocess support regardless of API server policy.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Executor encerrado.")
    except Exception as exc:
        print(f"Não foi possível iniciar ({type(exc).__name__}). Verifique configuração e dependências.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
