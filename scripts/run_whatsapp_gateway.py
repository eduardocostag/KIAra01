"""Run Kiara through OpenWA, without Chrome, extensions or interactive login."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_settings
from app.integrations.chatwoot import ChatwootClient
from app.integrations.openwa import OpenWAClient
from app.providers.omniroute import OmniRouteProvider
from app.whatsapp.engine import Engine
from app.whatsapp.omniroute import OmniRouteResponder
from app.whatsapp.store import DEFAULT_CONFIG, Store
from scripts.run_whatsapp_web import InstanceLock


async def run(args):
    if args.init_config:
        path = Path(args.init_config)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            json.dump(DEFAULT_CONFIG, handle, ensure_ascii=False, indent=2)
        print("Configuração criada com envios desativados. Cadastre contexto e contatos autorizados.")
        return
    if not args.config:
        raise ValueError("Informe --config com a política da operação.")
    if args.interval < 10 or not 1 <= args.max_daily <= 500:
        raise ValueError("Intervalo mínimo 10 segundos; limite diário entre 1 e 500.")
    directory = Path(args.data_dir).resolve()
    lock = InstanceLock(directory / "executor.lock")
    store = Store(directory / "history.sqlite3")
    try:
        from app.whatsapp.openwa import OpenWABrowser
        client = OpenWAClient(args.openwa_url, os.environ.get("OPENWA_API_KEY", ""), allow_private_hosts=True)
        browser = OpenWABrowser(client, args.session)
        if args.check_only:
            print(json.dumps({"gateway_status": await browser.status(),
                              "omniroute_key_configured": bool(os.environ.get("OMNIROUTE_API_KEY")),
                              "model_selected": bool(args.model), "messages_sent": 0}))
            return
        from app.whatsapp.chatwoot_handoff import ChatwootHandoffGuard
        chatwoot = ChatwootClient(os.environ.get("CHATWOOT_BASE_URL", "http://127.0.0.1:3005"),
                                  os.environ.get("CHATWOOT_API_ACCESS_TOKEN", ""),
                                  int(os.environ.get("CHATWOOT_ACCOUNT_ID", "0")),
                                  allow_private_hosts=True)
        browser = OpenWABrowser(client, args.session,
                                send_authorizer=ChatwootHandoffGuard(chatwoot, int(os.environ.get("CHATWOOT_INBOX_ID", "0"))))
        provider = OmniRouteProvider(os.environ.get("OMNIROUTE_API_KEY", ""), args.model,
                                     base_url=args.omniroute_url, max_output_tokens=400)
        engine = Engine(store, browser, responder=OmniRouteResponder(provider), max_daily=args.max_daily)
        print("Kiara via OpenWA. Sem extensão. Somente contatos autorizados; Ctrl+C encerra.")
        while True:
            try:
                # Re-read the policy on every cycle: a pause must not require a restart.
                store.configure(json.loads(Path(args.config).read_text(encoding="utf-8")))
                await engine.cycle()
                if engine.last_error:
                    print(engine.last_error)
                    engine.last_error = None
            except Exception as exc:
                # No request bodies, credentials or messages are written to logs.
                print(f"Operação pausada neste ciclo ({type(exc).__name__}); sem repetição de envio incerto.")
            if args.once:
                break
            await asyncio.sleep(args.interval)
    finally:
        store.close()
        lock.close()


def main():
    load_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="JSON com contexto, contatos e autorização da operação")
    parser.add_argument("--init-config", metavar="PATH", help="Criar configuração pausada e sair")
    parser.add_argument("--data-dir", default=str(ROOT / "data/openwa/kiara"))
    parser.add_argument("--openwa-url", default=os.environ.get("OPENWA_BASE_URL", "http://127.0.0.1:3006"))
    parser.add_argument("--session", default=os.environ.get("OPENWA_SESSION_ID", "kiara"))
    parser.add_argument("--omniroute-url", default=os.environ.get("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1"))
    parser.add_argument("--model", default=os.environ.get("OMNIROUTE_MODEL", ""), help="Modelo/combo explícito com custo verificado no OmniRoute")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--max-daily", type=int, default=50)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--once", action="store_true")
    try:
        asyncio.run(run(parser.parse_args()))
    except KeyboardInterrupt:
        print("Executor encerrado.")
    except Exception as exc:
        print(f"Não foi possível iniciar ({type(exc).__name__}). Verifique serviços e configuração.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
