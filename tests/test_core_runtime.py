from __future__ import annotations

from pathlib import Path

from kairos.config import KairosPaths, ensure_workspace
from kairos.core import AgentLoop, RuntimeContext, SessionEvent, SessionStore, parse_agent_command
from kairos.llm import ModelMessage, ModelReply
from kairos.messages import InboundMessage
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


def test_parse_agent_command_tool() -> None:
    command = parse_agent_command("/tool file.read path=README.md")

    assert command.kind == "tool"
    assert command.name == "file.read"
    assert command.arguments == {"path": "README.md"}


def test_agent_loop_records_plain_turn(tmp_path: Path) -> None:
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    context = RuntimeContext.local(paths, session_id="plain")

    result = AgentLoop(context).run_turn(InboundMessage(text="hello", sender_id="tester"))
    events = SessionStore(paths).read("plain")

    assert result.outbound
    assert "本地 MVP 模式" in result.outbound[0].text
    assert result.observations == ["model local/kairos-local-mvp: ok"]
    assert [event.role for event in events] == ["user", "assistant"]


def test_agent_loop_uses_injected_chat_provider(tmp_path: Path) -> None:
    class FakeProvider:
        name = "fake"
        model = "unit"

        def complete(self, system: str, messages: list[ModelMessage]) -> ModelReply:
            assert "Kairos" in system
            assert messages[-1].content == "hello model"
            return ModelReply(text="hello from model", provider=self.name, model=self.model)

    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    context = RuntimeContext.local(paths, session_id="provider")

    result = AgentLoop(context, chat_provider=FakeProvider()).run_turn(
        InboundMessage(text="hello model", sender_id="tester")
    )
    events = SessionStore(paths).read("provider")

    assert result.outbound[0].text == "hello from model"
    assert result.observations == ["model fake/unit: ok"]
    assert events[-1].content == "hello from model"


def test_agent_loop_tool_turn_uses_router_and_audit(tmp_path: Path) -> None:
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")
    context = RuntimeContext.local(paths, session_id="tool")

    result = AgentLoop(context).run_turn(
        InboundMessage(text="/tool file.read path=note.txt", sender_id="tester")
    )
    events = SessionStore(paths).read("tool")

    assert result.outbound
    assert "tool file.read: ok" in result.outbound[0].text
    assert "hello" in result.outbound[0].text
    assert [event.role for event in events] == ["user", "tool", "assistant"]
    assert (paths.audit / "tool-calls.jsonl").exists()
