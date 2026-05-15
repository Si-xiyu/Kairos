from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kairos.config import KairosPaths, ensure_workspace
from kairos.messages import InboundMessage
from kairos.core import AgentLoop
from kairos.permissions import AutonomyLevel, PermissionManager


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

    print("smoke_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
