from __future__ import annotations

import argparse
from pathlib import Path

from kairos.config import KairosPaths, ensure_workspace
from kairos.core import SessionEvent, SessionStore
from kairos.permissions import AuditLogger, AutonomyLevel, PermissionManager
from kairos.tools import ToolRouter
from kairos.tools.native import build_native_registry, parse_tool_arguments


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kairos")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Create the local .kairos workspace.")
    init_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")

    status_parser = sub.add_parser("status", help="Show Kairos workspace status.")
    status_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")

    tools_parser = sub.add_parser("tools", help="List registered native tools.")
    tools_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")

    run_tool_parser = sub.add_parser("run-tool", help="Run a registered tool through permissions.")
    run_tool_parser.add_argument("name", help="Tool name, for example file.list.")
    run_tool_parser.add_argument("--args", default="{}", help="JSON object passed as tool arguments.")
    run_tool_parser.add_argument(
        "--arg",
        action="append",
        default=[],
        help="Single key=value argument. May be repeated. Overrides --args.",
    )
    run_tool_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    run_tool_parser.add_argument("--autonomy", type=int, default=3, help="Autonomy level for this call.")

    record_parser = sub.add_parser("record", help="Append a message to a JSONL session.")
    record_parser.add_argument("role", choices=["system", "user", "assistant", "tool"])
    record_parser.add_argument("content")
    record_parser.add_argument("--session", default="default")
    record_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")

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


def cmd_tools(root: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    registry = build_native_registry(paths)
    for spec in registry.list():
        print(f"{spec.name}\t{spec.risk_level}\t{spec.source}\t{spec.description}")
    return 0


def cmd_run_tool(root: str, name: str, raw_args: str, kv_args: list[str], autonomy: int) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    registry = build_native_registry(paths)
    permissions = PermissionManager(AutonomyLevel(autonomy))
    router = ToolRouter(registry, permissions, AuditLogger(paths))
    arguments = parse_tool_arguments(raw_args)
    arguments.update(_parse_key_value_args(kv_args))
    result = router.call(name, arguments)
    print(f"status: {result.status}")
    if result.preview:
        print(result.preview)
    return 0 if result.status == "ok" else 1


def cmd_record(root: str, session: str, role: str, content: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    store = SessionStore(paths)
    path = store.append(session, SessionEvent(role=role, content=content))
    print(f"recorded: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init(args.root)
    if args.command == "status":
        return cmd_status(args.root)
    if args.command == "tools":
        return cmd_tools(args.root)
    if args.command == "run-tool":
        return cmd_run_tool(args.root, args.name, args.args, args.arg, args.autonomy)
    if args.command == "record":
        return cmd_record(args.root, args.session, args.role, args.content)
    if args.command in {"chat", "daemon"}:
        print(f"`kairos {args.command}` is reserved by the runtime skeleton.")
        return 0

    parser.print_help()
    return 0


def _parse_key_value_args(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"--arg must use key=value format: {item}")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
