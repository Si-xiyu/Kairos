from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from kairos.channels import CLIChannel
from kairos.config import KairosPaths, ensure_workspace
from kairos.core import AgentLoop, RuntimeContext, SessionEvent, SessionStore
from kairos.delivery import DeliveryQueue, DeliveryRunner
from kairos.lifelog import DailyJournalStore
from kairos.memory import MemoryEntry, MemoryStore, MemoryType
from kairos.messages import InboundMessage
from kairos.permissions import AuditLogger, AutonomyLevel, PermissionManager
from kairos.presence import HeartbeatPolicy, HeartbeatState, should_run
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

    memory_save = sub.add_parser("memory-save", help="Save a confirmed memory entry.")
    memory_save.add_argument("name")
    memory_save.add_argument("description")
    memory_save.add_argument("content")
    memory_save.add_argument("--type", default="user", choices=[item.value for item in MemoryType])
    memory_save.add_argument("--candidate", action="store_true")
    memory_save.add_argument("--root", default=".")

    memory_list = sub.add_parser("memory-list", help="List memory entries.")
    memory_list.add_argument("--include-candidates", action="store_true")
    memory_list.add_argument("--root", default=".")

    journal_create = sub.add_parser("journal-create", help="Create a daily Markdown journal.")
    journal_create.add_argument("--date", default=None, help="YYYY-MM-DD. Defaults to today.")
    journal_create.add_argument("--root", default=".")

    journal_append = sub.add_parser("journal-append", help="Append a fragment to a daily journal.")
    journal_append.add_argument("heading")
    journal_append.add_argument("text")
    journal_append.add_argument("--date", default=None, help="YYYY-MM-DD. Defaults to today.")
    journal_append.add_argument("--root", default=".")

    delivery_enqueue = sub.add_parser("delivery-enqueue", help="Queue an outbound CLI delivery.")
    delivery_enqueue.add_argument("text")
    delivery_enqueue.add_argument("--channel", default="cli")
    delivery_enqueue.add_argument("--to", default="local-user")
    delivery_enqueue.add_argument("--root", default=".")

    delivery_process = sub.add_parser("delivery-process", help="Process pending CLI deliveries once.")
    delivery_process.add_argument("--root", default=".")

    heartbeat_check = sub.add_parser("heartbeat-check", help="Evaluate heartbeat policy once.")
    heartbeat_check.add_argument("--user-active", action="store_true")
    heartbeat_check.add_argument("--dnd", action="store_true")
    heartbeat_check.add_argument("--root", default=".")

    chat_once = sub.add_parser("chat-once", help="Run one deterministic AgentLoop turn.")
    chat_once.add_argument("text")
    chat_once.add_argument("--session", default="default")
    chat_once.add_argument("--root", default=".")
    chat_once.add_argument("--autonomy", type=int, default=3)

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


def cmd_memory_save(
    root: str,
    name: str,
    description: str,
    content: str,
    mem_type: str,
    candidate: bool,
) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    store = MemoryStore(paths)
    path = store.save(
        MemoryEntry(
            name=name,
            description=description,
            type=MemoryType(mem_type),
            content=content,
        ),
        candidate=candidate,
    )
    print(f"memory: {path}")
    return 0


def cmd_memory_list(root: str, include_candidates: bool) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    entries = MemoryStore(paths).list(include_candidates=include_candidates)
    for entry in entries:
        print(f"{entry.name}\t{entry.type.value}\t{entry.description}")
    return 0


def cmd_journal_create(root: str, raw_date: str | None) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    journal_date = _parse_date(raw_date)
    path = DailyJournalStore(paths).create(journal_date)
    print(f"journal: {path}")
    return 0


def cmd_journal_append(root: str, raw_date: str | None, heading: str, text: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    journal_date = _parse_date(raw_date)
    path = DailyJournalStore(paths).append_fragment(journal_date, heading, text)
    print(f"journal: {path}")
    return 0


def cmd_delivery_enqueue(root: str, channel: str, to: str, text: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    delivery_id = DeliveryQueue(paths).enqueue(channel, to, text)
    print(f"delivery: {delivery_id}")
    return 0


def cmd_delivery_process(root: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    channels = {"cli": CLIChannel()}

    def deliver(channel: str, to: str, text: str) -> bool:
        if channel not in channels:
            return False
        return channels[channel].send(to, text)

    stats = DeliveryRunner(DeliveryQueue(paths), deliver).process_once()
    for key, value in stats.items():
        print(f"{key}: {value}")
    return 0


def cmd_heartbeat_check(root: str, user_active: bool, dnd: bool) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    now = datetime.now(timezone.utc)
    allowed, reason = should_run(
        now,
        HeartbeatPolicy(),
        HeartbeatState(),
        user_active=user_active,
        do_not_disturb=dnd,
    )
    print(f"allowed: {allowed}")
    print(f"reason: {reason}")
    return 0


def cmd_chat_once(root: str, session: str, text: str, autonomy: int) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    context = RuntimeContext.local(paths, session_id=session, autonomy_level=AutonomyLevel(autonomy))
    result = AgentLoop(context).run_turn(
        InboundMessage(text=text, sender_id="cli-user", channel="cli", peer_id="cli-user")
    )
    channel = CLIChannel()
    for outbound in result.outbound:
        channel.send(outbound.to, outbound.text)
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
    if args.command == "memory-save":
        return cmd_memory_save(
            args.root,
            args.name,
            args.description,
            args.content,
            args.type,
            args.candidate,
        )
    if args.command == "memory-list":
        return cmd_memory_list(args.root, args.include_candidates)
    if args.command == "journal-create":
        return cmd_journal_create(args.root, args.date)
    if args.command == "journal-append":
        return cmd_journal_append(args.root, args.date, args.heading, args.text)
    if args.command == "delivery-enqueue":
        return cmd_delivery_enqueue(args.root, args.channel, args.to, args.text)
    if args.command == "delivery-process":
        return cmd_delivery_process(args.root)
    if args.command == "heartbeat-check":
        return cmd_heartbeat_check(args.root, args.user_active, args.dnd)
    if args.command == "chat-once":
        return cmd_chat_once(args.root, args.session, args.text, args.autonomy)
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


def _parse_date(raw: str | None) -> date:
    if raw is None:
        return date.today()
    return date.fromisoformat(raw)


if __name__ == "__main__":
    raise SystemExit(main())
