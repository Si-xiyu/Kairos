from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kairos.config import KairosPaths, ensure_workspace
from kairos.messages import InboundMessage
from kairos.core import AgentLoop, RuntimeContext, SessionEvent, SessionStore
from kairos.delivery import DeliveryQueue, DeliveryRunner
from kairos.lifelog import DailyJournalStore, JournalDraftBuilder, ReflectionFragment, write_reflection_draft
from kairos.memory import MemoryEntry, MemoryStore, MemoryType
from kairos.memory.candidates import MemoryCandidateExtractor, save_candidates
from kairos.permissions import AuditLogger, AutonomyLevel, PermissionManager
from kairos.presence import HeartbeatPolicy, HeartbeatState, should_run
from kairos.tools import ToolRouter
from kairos.tools.native import build_native_registry


def main() -> int:
    with TemporaryDirectory() as tmp:
        paths = KairosPaths.from_root(Path(tmp))
        ensure_workspace(paths)
        assert paths.home.exists()
        assert (paths.home / "config.toml").exists()

        result = AgentLoop().run_turn(InboundMessage(text="hello", sender_id="tester"))
        assert result.outbound

        decision = PermissionManager(AutonomyLevel.LOW_RISK_AUTO).decide("low")
        assert decision.decision == "allow"

        sessions = SessionStore(paths)
        sessions.append("smoke", SessionEvent(role="user", content="hello"))
        assert sessions.read("smoke")[0].content == "hello"

        registry = build_native_registry(paths)
        router = ToolRouter(
            registry,
            PermissionManager(AutonomyLevel.LOW_RISK_AUTO),
            AuditLogger(paths),
        )
        listed = router.call("file.list", {"path": "."})
        assert listed.status == "ok"
        assert (paths.audit / "tool-calls.jsonl").exists()

        memory_path = MemoryStore(paths).save(
            MemoryEntry(
                name="smoke_memory",
                description="Smoke test memory",
                type=MemoryType.USER,
                content="Memory content",
            )
        )
        assert memory_path.exists()

        journal_path = DailyJournalStore(paths).create(date.today())
        assert journal_path.exists()

        queue = DeliveryQueue(paths)
        delivery_id = queue.enqueue("cli", "tester", "hello")
        stats = DeliveryRunner(queue, lambda channel, to, text: True).process_once()
        assert stats["delivered"] == 1
        assert not (paths.delivery_pending / f"{delivery_id}.json").exists()

        allowed, reason = should_run(
            datetime.now(timezone.utc),
            HeartbeatPolicy(),
            HeartbeatState(),
            user_active=True,
        )
        assert allowed is False
        assert reason == "user_active"

        turn = AgentLoop(RuntimeContext.local(paths, session_id="agent-smoke")).run_turn(
            InboundMessage(text="/tool file.list path=.", sender_id="tester")
        )
        assert "tool file.list: ok" in turn.outbound[0].text

        draft = JournalDraftBuilder.from_fragments(
            date.today(),
            [ReflectionFragment(text="我喜欢先讨论架构，今天很有能量", source="smoke")],
        )
        write_reflection_draft(DailyJournalStore(paths), draft)
        candidate_paths = save_candidates(
            MemoryStore(paths),
            MemoryCandidateExtractor.extract_from_draft(draft),
        )
        assert candidate_paths

        from kairos.cli import main as cli_main

        assert cli_main(["bootstrap", "--root", str(paths.root)]) == 0
        assert cli_main(["doctor", "--root", str(paths.root)]) == 0

    print("smoke_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
