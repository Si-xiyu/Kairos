from __future__ import annotations

import argparse
from pathlib import Path

from kairos.backend.http import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kairos-app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", default=".", help="Kairos project root. Defaults to current directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_server(host=args.host, port=args.port, root=Path(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
