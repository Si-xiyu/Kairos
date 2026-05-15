from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from kairos.channels import ChannelManager, CLIChannel
from kairos.config import KairosPaths, ensure_workspace
from kairos.core import AgentLoop, RuntimeContext, SessionEvent, SessionStore
from kairos.delivery import DeliveryQueue, DeliveryRunner
from kairos.lifelog import DailyJournalStore, JournalDraftBuilder, ReflectionFragment, write_reflection_draft
from kairos.memory import MemoryEntry, MemoryStore, MemoryType
from kairos.memory.candidates import MemoryCandidateExtractor, save_candidates
from kairos.messages import InboundMessage
from kairos.permissions import AuditLogger, AutonomyLevel, PermissionManager
from kairos.presence import (
    DaemonRuntime,
    HeartbeatPolicy,
    HeartbeatState,
    PresenceEvent,
    ScheduleStore,
    ScheduledJob,
    should_run,
)
from kairos.messages import OutboundMessage
from kairos.tools import ToolRouter
from kairos.tools.native import build_native_registry, parse_tool_arguments


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kairos")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="Create the local .kairos workspace.")
    init_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")

    bootstrap_parser = sub.add_parser("bootstrap", help="Initialize Kairos and install first-round defaults.")
    bootstrap_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    bootstrap_parser.add_argument("--force", action="store_true", help="Overwrite default jobs if they exist.")

    doctor_parser = sub.add_parser("doctor", help="Inspect the local Kairos workspace.")
    doctor_parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")

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

    reflect = sub.add_parser("reflect", help="Turn a text fragment into journal sections and memory candidates.")
    reflect.add_argument("text")
    reflect.add_argument("--date", default=None, help="YYYY-MM-DD. Defaults to today.")
    reflect.add_argument("--source", default="cli")
    reflect.add_argument("--no-candidates", action="store_true")
    reflect.add_argument("--root", default=".")

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

    schedule_add = sub.add_parser("schedule-add", help="Add a lightweight presence schedule.")
    schedule_add.add_argument("id")
    schedule_add.add_argument("name")
    schedule_add.add_argument("--kind", choices=["at", "every"], default="every")
    schedule_add.add_argument("--at", default=None, help="ISO datetime for kind=at.")
    schedule_add.add_argument("--seconds", type=int, default=3600, help="Interval seconds for kind=every.")
    schedule_add.add_argument("--event", default="daily_journal_check")
    schedule_add.add_argument("--message", default=None)
    schedule_add.add_argument("--due-now", action="store_true")
    schedule_add.add_argument("--root", default=".")

    daemon_tick = sub.add_parser("daemon-tick", help="Run one daemon scheduler/delivery tick.")
    daemon_tick.add_argument("--root", default=".")

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


def cmd_bootstrap(root: str, force: bool) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    store = ScheduleStore(paths)
    jobs = store.load()
    default_job = ScheduledJob(
        id="nightly-journal",
        name="Nightly Journal Check",
        schedule={"kind": "daily", "hour": 23, "minute": 0},
        payload={
            "kind": "presence_event",
            "event": "daily_journal_check",
            "payload": {
                "message": "今天还没有留下记录。要不要随便丢几个碎片给我，我帮你整理成日记？",
                "channel": "cli",
                "to": "local-user",
            },
        },
    )
    if force or not any(job.id == default_job.id for job in jobs):
        store.add(default_job)
        action = "installed"
    else:
        action = "kept"
    print(f"workspace: {paths.home}")
    print(f"default_nightly_journal: {action}")
    return 0


def cmd_status(root: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    print(f"root: {paths.root}")
    print(f"kairos_home: {paths.home}")
    print(f"initialized: {paths.home.exists()}")
    return 0


def cmd_doctor(root: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    print(f"root: {paths.root}")
    print(f"kairos_home: {paths.home}")
    print(f"initialized: {paths.home.exists()}")
    print(f"conversations: {_count_files(paths.conversations, '*.jsonl')}")
    print(f"journals: {_count_files(paths.journal, '*.md')}")
    print(f"memories: {len(MemoryStore(paths).list()) if paths.memory.exists() else 0}")
    print(
        "memory_candidates: "
        f"{len(MemoryStore(paths).list(include_candidates=True)) - len(MemoryStore(paths).list()) if paths.memory.exists() else 0}"
    )
    print(f"schedules: {len(ScheduleStore(paths).load()) if paths.schedules.exists() else 0}")
    print(f"delivery_pending: {_count_files(paths.delivery_pending, '*.json')}")
    print(f"delivery_failed: {_count_files(paths.delivery_failed, '*.json')}")
    print(f"audit_events: {_count_lines(paths.audit / 'tool-calls.jsonl')}")
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


def cmd_reflect(
    root: str,
    raw_date: str | None,
    text: str,
    source: str,
    no_candidates: bool,
) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    journal_date = _parse_date(raw_date)
    fragment = ReflectionFragment(text=text, source=source)
    draft = JournalDraftBuilder.from_fragments(journal_date, [fragment])
    journal_path = write_reflection_draft(DailyJournalStore(paths), draft)
    print(f"journal: {journal_path}")

    candidates = MemoryCandidateExtractor.extract_from_draft(draft)
    saved = [] if no_candidates else save_candidates(MemoryStore(paths), candidates)
    print(f"candidates: {len(candidates)}")
    for path in saved:
        print(f"candidate: {path}")
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


def cmd_schedule_add(
    root: str,
    job_id: str,
    name: str,
    kind: str,
    raw_at: str | None,
    seconds: int,
    event: str,
    message: str | None,
    due_now: bool,
) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    now = datetime.now(timezone.utc)
    schedule: dict[str, object]
    if kind == "at":
        if raw_at is None and not due_now:
            raise ValueError("--at is required for kind=at unless --due-now is used.")
        schedule = {"kind": "at", "at": (now if due_now else _parse_datetime(raw_at)).isoformat()}
    else:
        schedule = {"kind": "every", "seconds": seconds}

    payload = {
        "kind": "presence_event",
        "event": event,
        "payload": {
            "message": message,
            "channel": "cli",
            "to": "local-user",
        },
    }
    job = ScheduledJob(
        id=job_id,
        name=name,
        schedule=schedule,
        payload=payload,
        next_run_at=now if due_now else None,
    )
    ScheduleStore(paths).add(job)
    print(f"schedule: {job_id}")
    return 0


def cmd_daemon_tick(root: str) -> int:
    paths = KairosPaths.from_root(Path(root))
    ensure_workspace(paths)
    runtime = DaemonRuntime(
        schedule_store=ScheduleStore(paths),
        delivery_queue=DeliveryQueue(paths),
        channel_manager=ChannelManager([CLIChannel()]),
        presence_handler=_presence_handler,
    )
    result = runtime.tick()
    print(f"due_jobs: {result.due_jobs}")
    print(f"enqueued: {result.enqueued}")
    print(f"failed_jobs: {result.failed_jobs}")
    for key, value in result.delivery.items():
        print(f"delivery_{key}: {value}")
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
    if args.command == "bootstrap":
        return cmd_bootstrap(args.root, args.force)
    if args.command == "doctor":
        return cmd_doctor(args.root)
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
    if args.command == "reflect":
        return cmd_reflect(args.root, args.date, args.text, args.source, args.no_candidates)
    if args.command == "delivery-enqueue":
        return cmd_delivery_enqueue(args.root, args.channel, args.to, args.text)
    if args.command == "delivery-process":
        return cmd_delivery_process(args.root)
    if args.command == "heartbeat-check":
        return cmd_heartbeat_check(args.root, args.user_active, args.dnd)
    if args.command == "schedule-add":
        return cmd_schedule_add(
            args.root,
            args.id,
            args.name,
            args.kind,
            args.at,
            args.seconds,
            args.event,
            args.message,
            args.due_now,
        )
    if args.command == "daemon-tick":
        return cmd_daemon_tick(args.root)
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


def _parse_datetime(raw: str | None) -> datetime:
    if raw is None:
        raise ValueError("datetime value is required")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _presence_handler(event: PresenceEvent, now: datetime):
    message = event.payload.get("message") or _default_presence_message(event)
    if not message:
        return []
    channel = str(event.payload.get("channel", "cli"))
    to = str(event.payload.get("to", "local-user"))
    return [OutboundMessage(channel=channel, to=to, text=str(message))]


def _default_presence_message(event: PresenceEvent) -> str:
    if event.event == "daily_journal_check":
        return "今天还没有留下记录。要不要随便丢几个碎片给我，我帮你整理成日记？"
    if event.event == "heartbeat":
        return "Kairos heartbeat check."
    return f"Kairos presence event: {event.event}"


def _count_files(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob(pattern))


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8").splitlines())


if __name__ == "__main__":
    raise SystemExit(main())
