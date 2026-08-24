from __future__ import annotations

import argparse
import asyncio

from app.bootstrap import build_app
from app.config import load_settings


def confirm(summary: str) -> bool:
    answer = input(f"Confirmar ação sensível? {summary}\nDigite SIM: ").strip().casefold()
    return answer == "sim"


async def interactive() -> None:
    settings = load_settings()
    core, kill_switch = build_app(settings, confirm=confirm)
    print("Kiara iniciada. Digite um pedido; /sair encerra; /parar aciona o kill switch.")
    await core.astart()
    try:
        while True:
            message = await asyncio.to_thread(input, "Você> ")
            if message.strip().casefold() == "/sair":
                break
            if message.strip().casefold() == "/parar":
                kill_switch.trigger()
                print("Kiara> Todas as ações foram interrompidas.")
                continue
            print("Kiara>", await core.handle(message))
    finally:
        await core.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiara Assistant")
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument("--console", action="store_true", help="usa a interface de terminal")
    args = parser.parse_args()
    if args.diagnostics:
        from app.diagnostics import main as diagnostics_main
        diagnostics_main()
        return
    if args.console:
        asyncio.run(interactive())
        return
    try:
        from app.bootstrap import run_desktop_app

        raise SystemExit(run_desktop_app(load_settings()))
    except ImportError as exc:
        if exc.name != "PySide6":
            raise
        print("PySide6 não instalado; iniciando em modo console.")
        asyncio.run(interactive())


if __name__ == "__main__":
    main()
