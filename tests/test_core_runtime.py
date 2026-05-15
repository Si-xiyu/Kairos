from __future__ import annotations

from pathlib import Path

from kairos.config import KairosPaths, ensure_workspace
from kairos.core import SessionEvent, SessionStore
from kairos.permissions import AuditLogger, AutonomyLevel, PermissionManager
from kairos.tools import ToolRouter
from kairos.tools.native import build_native_registry, parse_tool_arguments


def test_session_store_round_trip(tmp_path: Path) -> None:
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    store = SessionStore(paths)

    store.append("today", SessionEvent(role="user", content="hello"))
    events = store.read("today")

    assert len(events) == 1
    assert events[0].role == "user"
    assert events[0].content == "hello"


def test_tool_router_allows_low_risk_and_audits(tmp_path: Path) -> None:
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    registry = build_native_registry(paths)
    router = ToolRouter(
        registry,
        PermissionManager(AutonomyLevel.LOW_RISK_AUTO),
        AuditLogger(paths),
    )

    result = router.call("file.list", {"path": "."})

    assert result.status == "ok"
    assert (paths.audit / "tool-calls.jsonl").exists()


def test_tool_router_blocks_medium_without_approval(tmp_path: Path) -> None:
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    registry = build_native_registry(paths)
    router = ToolRouter(registry, PermissionManager(AutonomyLevel.LOW_RISK_AUTO))

    result = router.call("file.write", {"path": "note.txt", "content": "hello"})

    assert result.status == "blocked"
    assert not (tmp_path / "note.txt").exists()


def test_file_tool_rejects_path_escape(tmp_path: Path) -> None:
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    registry = build_native_registry(paths)
    router = ToolRouter(registry, PermissionManager(AutonomyLevel.LOW_RISK_AUTO))

    result = router.call("file.read", {"path": "../outside.txt"})

    assert result.status == "error"
    assert "escapes project root" in result.preview


def test_parse_tool_arguments_accepts_escaped_json() -> None:
    assert parse_tool_arguments('{\\"path\\":\\".\\"}') == {"path": "."}
