from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal

from kairos.tools.registry import RiskLevel

Decision = Literal["allow", "ask", "deny"]


class AutonomyLevel(IntEnum):
    PASSIVE = 0
    NOTIFY_ONLY = 1
    DRAFT_ONLY = 2
    LOW_RISK_AUTO = 3
    APPROVED_SCOPE_AUTO = 4
    HIGH_AUTONOMY_AGENT = 5


@dataclass(frozen=True)
class PermissionDecision:
    decision: Decision
    reason: str


class PermissionManager:
    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.NOTIFY_ONLY) -> None:
        self.autonomy_level = autonomy_level

    def decide(self, risk_level: RiskLevel) -> PermissionDecision:
        if risk_level == "low" and self.autonomy_level >= AutonomyLevel.LOW_RISK_AUTO:
            return PermissionDecision("allow", "Low-risk tool allowed by autonomy level.")
        if risk_level in {"high", "critical"} and self.autonomy_level < AutonomyLevel.APPROVED_SCOPE_AUTO:
            return PermissionDecision("ask", "High-risk tool requires explicit approval.")
        if self.autonomy_level == AutonomyLevel.PASSIVE:
            return PermissionDecision("ask", "Passive mode requires user confirmation.")
        return PermissionDecision("ask", "No explicit allow rule matched.")
