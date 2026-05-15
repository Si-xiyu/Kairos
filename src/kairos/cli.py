from __future__ import annotations

import argparse
from pathlib import Path

from kairos.config import KairosPaths, ensure_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kairos")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Create the local .kairos workspace.")
    init_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")

    status_parser = sub.add_parser("status", help="Show Kairos workspace status.")
    status_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")

    sub.add_parser("chat", help="Placeholder for interactive agent chat.")
    sub.add_parser("daemon", help="Placeholder for long-running Kairos daemon.")
    return parser


def cmd_init(root: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    print(f"Initialized Kairos workspace at {paths.home}")
    return 0


def cmd_status(root: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    print(f"root: {paths.root}")
    print(f"kairos_home: {paths.home}")
    print(f"initialized: {paths.home.exists()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init(args.root)
    if args.command == "status":
        return cmd_status(args.root)
    if args.command in {"chat", "daemon"}:
        print(f"`kairos {args.command}` is reserved by the runtime skeleton.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
