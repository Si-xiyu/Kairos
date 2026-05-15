from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from kairos.permissions.audit import AuditEvent, AuditLogger
from kairos.permissions.model import PermissionManager
from kairos.tools.registry import ToolRegistry, ToolResult

ExecutionStatus = Literal["ok", "error", "blocked"]


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_name: str
    status: ExecutionStatus
    preview: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class ToolRouter:
    def __init__(
        self,
        registry: ToolRegistry,
        permissions: PermissionManager,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.registry = registry
        self.permissions = permissions
        self.audit_logger = audit_logger

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> ToolExecutionResult:
        arguments = arguments or {}
        spec = self.registry.get(name)
        decision = self.permissions.decide(spec.risk_level)

        self._audit(
            AuditEvent(
                action=f"tool:{name}",
                decision=decision.decision,
                reason=decision.reason,
                metadata={"risk_level": spec.risk_level, "source": spec.source},
            )
        )

        if decision.decision != "allow":
            return ToolExecutionResult(
                tool_name=name,
                status="blocked",
                preview=decision.reason,
                data={"decision": decision.decision},
            )

        try:
            result: ToolResult = spec.handler(**arguments)
        except Exception as exc:
            self._audit(
                AuditEvent(
                    action=f"tool:{name}:error",
                    decision="error",
                    reason=str(exc),
                    metadata={"risk_level": spec.risk_level, "source": spec.source},
                )
            )
            return ToolExecutionResult(tool_name=name, status="error", preview=str(exc))

        return ToolExecutionResult(
            tool_name=name,
            status=result.status,
            preview=result.preview,
            data=result.data,
        )

    def _audit(self, event: AuditEvent) -> None:
        if self.audit_logger is not None:
            self.audit_logger.append(event)
