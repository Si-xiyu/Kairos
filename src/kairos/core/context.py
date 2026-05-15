from __future__ import annotations

from dataclasses import dataclass

from kairos.config import KairosPaths
from kairos.core.session import SessionStore
from kairos.permissions.audit import AuditLogger
from kairos.permissions.model import AutonomyLevel, PermissionManager
from kairos.tools.native import build_native_registry
from kairos.tools.router import ToolRouter


@dataclass(frozen=True)
class RuntimeContext:
    paths: KairosPaths
    session_id: str
    tool_router: ToolRouter
    sessions: SessionStore

    @classmethod
    def local(
        cls,
        paths: KairosPaths,
        session_id: str = "default",
        autonomy_level: AutonomyLevel = AutonomyLevel.LOW_RISK_AUTO,
    ) -> "RuntimeContext":
        permissions = PermissionManager(autonomy_level)
        tool_router = ToolRouter(
            build_native_registry(paths),
            permissions,
            AuditLogger(paths),
        )
        return cls(
            paths=paths,
            session_id=session_id,
            tool_router=tool_router,
            sessions=SessionStore(paths),
        )
