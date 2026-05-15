from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kairos.config import KairosPaths, ensure_workspace
from kairos.messages import InboundMessage
from kairos.core import AgentLoop, SessionEvent, SessionStore
from kairos.permissions import AuditLogger, AutonomyLevel, PermissionManager
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

    print("smoke_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
