from __future__ import annotations

from pathlib import Path

from kairos.config import KairosPaths, ensure_workspace
from kairos.core import AgentLoop, RuntimeContext, SessionEvent, SessionStore, parse_agent_command
from kairos.core.context_window import ContextPolicy, ContextWindow
from kairos.llm import ModelMessage, ModelReply, ModelTool, ModelToolCall
from kairos.memory import MemoryStore
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


def test_advanced_tools_search_memory_and_environment_context(tmp_path: Path, monkeypatch) -> None:
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    fixture = tmp_path / "search-fixture.json"
    fixture.write_text(
        """
        {
          "results": [
            {"title": "Lunch noodles", "url": "https://example.test/noodles", "snippet": "warm lunch near office"},
            {"title": "Unrelated", "url": "https://example.test/other", "snippet": "nothing"}
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("KAIROS_WEB_SEARCH_FIXTURE", "search-fixture.json")
    monkeypatch.setenv("KAIROS_LOCATION_NAME", "Shanghai")
    monkeypatch.setenv("KAIROS_WEATHER_SUMMARY", "light rain")
    monkeypatch.setenv("KAIROS_WEATHER_TEMPERATURE_C", "22")
    registry = build_native_registry(paths)
    router = ToolRouter(
        registry,
        PermissionManager(AutonomyLevel.LOW_RISK_AUTO),
        AuditLogger(paths),
    )

    saved = router.call(
        "memory.save_candidate",
        {
            "name": "prefers_warm_lunch",
            "description": "User prefers warm lunch on rainy days.",
            "content": "When it rains, suggest warm soup or noodles.",
            "type": "user",
            "reason": "lunch preference",
        },
    )
    memory = router.call("memory.search", {"query": "warm lunch", "include_candidates": True})
    search = router.call("web.search", {"query": "lunch", "limit": 3})
    location = router.call("location.current")
    weather = router.call("weather.current")

    assert {spec.name for spec in registry.list()} >= {
        "web.search",
        "weather.current",
        "location.current",
        "memory.search",
        "memory.save_candidate",
    }
    assert saved.status == "ok"
    assert memory.status == "ok"
    assert memory.data["matches"][0]["name"] == "prefers_warm_lunch"
    assert search.data["configured"] is True
    assert search.data["results"][0]["title"] == "Lunch noodles"
    assert location.data["name"] == "Shanghai"
    assert weather.data["summary"] == "light rain"
    assert len((paths.audit / "tool-calls.jsonl").read_text(encoding="utf-8").splitlines()) >= 10


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
    assert "KAIROS_LLM_PROVIDER" in result.outbound[0].text
    assert result.observations == ["model local/kairos-local-mvp: ok"]
    assert [event.role for event in events] == ["user", "assistant"]


def test_agent_loop_uses_injected_chat_provider(tmp_path: Path) -> None:
    class FakeProvider:
        name = "fake"
        model = "unit"

        def complete(
            self,
            system: str,
            messages: list[ModelMessage],
            tools: list[ModelTool] | None = None,
        ) -> ModelReply:
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


def test_agent_loop_model_tool_call_round_trips_through_router(tmp_path: Path) -> None:
    class ToolCallingProvider:
        name = "fake"
        model = "tool-unit"

        def __init__(self) -> None:
            self.calls = 0

        def complete(
            self,
            system: str,
            messages: list[ModelMessage],
            tools: list[ModelTool] | None = None,
        ) -> ModelReply:
            self.calls += 1
            if self.calls == 1:
                assert tools and any(tool.name == "file__read" for tool in tools)
                return ModelReply(
                    text="",
                    provider=self.name,
                    model=self.model,
                    tool_calls=(
                        ModelToolCall(
                            id="call_1",
                            name="file__read",
                            arguments={"path": "note.txt"},
                        ),
                    ),
                )
            assert any(message.role == "tool" and "hello" in message.content for message in messages)
            return ModelReply(text="The file says hello.", provider=self.name, model=self.model)

    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")
    context = RuntimeContext.local(paths, session_id="model-tool")
    provider = ToolCallingProvider()

    result = AgentLoop(context, chat_provider=provider).run_turn(
        InboundMessage(text="read note.txt", sender_id="tester")
    )
    events = SessionStore(paths).read("model-tool")

    assert result.outbound[0].text == "The file says hello."
    assert provider.calls == 2
    assert [event.role for event in events] == ["user", "assistant", "tool", "assistant"]
    assert events[1].metadata["tool_calls"][0]["name"] == "file__read"
    assert events[2].metadata["tool"] == "file.read"
    assert events[2].metadata["tool_call_id"] == "call_1"
    assert (paths.audit / "tool-calls.jsonl").exists()


def test_context_window_replaces_large_tool_results_and_summarizes(tmp_path: Path) -> None:
    class SummaryProvider:
        name = "fake"
        model = "summary"

        def complete(
            self,
            system: str,
            messages: list[ModelMessage],
            tools: list[ModelTool] | None = None,
        ) -> ModelReply:
            assert "Summarize" in system
            return ModelReply(text="Compressed context summary.", provider=self.name, model=self.model)

    events = [
        SessionEvent(role="user", content="start"),
        SessionEvent(
            role="tool",
            content="x" * 200,
            metadata={"tool": "file.read", "status": "ok", "tool_call_id": "call_1"},
        ),
        SessionEvent(role="assistant", content="middle" * 80),
        SessionEvent(role="user", content="latest"),
    ]
    window = ContextWindow(
        ContextPolicy(tool_placeholder_after_chars=20, summarize_after_chars=120, preserve_recent_messages=1)
    )

    result = window.build("system", events, SummaryProvider())

    assert result.summary == "Compressed context summary."
    assert result.messages[0].content.startswith("Earlier context summary")
    assert any("level1" in observation for observation in result.observations)
    assert any("level2" in observation for observation in result.observations)


def test_agent_loop_saves_memory_candidate_from_valuable_user_text(tmp_path: Path) -> None:
    paths = KairosPaths.from_root(tmp_path)
    ensure_workspace(paths)
    context = RuntimeContext.local(paths, session_id="memory")

    result = AgentLoop(context).run_turn(
        InboundMessage(text="Please remember: I prefer architecture before implementation.", sender_id="tester")
    )
    memories = MemoryStore(paths).list(include_candidates=True)

    assert any(observation.startswith("memory candidate:") for observation in result.observations)
    assert memories
    assert memories[0].source == "session/memory"


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
