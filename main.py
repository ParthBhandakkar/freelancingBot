"""Server entrypoint for the freelancing bot dashboard and API."""
from __future__ import annotations

import argparse

from uvicorn import run as uvicorn_run

from config import settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the freelancing bot server")
    parser.add_argument("--host", default=settings.server_host)
    parser.add_argument("--port", type=int, default=settings.server_port)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--headless", action="store_true")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    if args.headless:
        settings.headless = True
    uvicorn_run("server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
