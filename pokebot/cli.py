"""Interface en ligne de commande : `serve` (UI + planificateur) ou `scan` (unique)."""
from __future__ import annotations

import argparse

from .config import settings


def cmd_serve() -> None:
    import uvicorn

    uvicorn.run("pokebot.main:app", host=settings.host, port=settings.port, reload=False)


def cmd_scan() -> None:
    from .core.scanner import run_scan
    from .database import init_db
    from .seed import seed_defaults
    from .utils.logging import setup_logging

    setup_logging()
    init_db()
    seed_defaults()
    scan_id = run_scan("manual")
    print(f"Scan termine (id={scan_id}).")


def main() -> None:
    parser = argparse.ArgumentParser(prog="pokebot", description="Bot d'alerte de prix Pokemon")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Lance l'interface web + le planificateur (defaut)")
    sub.add_parser("scan", help="Lance un seul cycle de scan puis quitte")
    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan()
    else:
        cmd_serve()


if __name__ == "__main__":
    main()
