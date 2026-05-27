from __future__ import annotations

from dataclasses import dataclass

from kairos.core.session import SessionEvent


@dataclass(frozen=True)
class PromptBundle:
    system: str
    recent_messages: list[SessionEvent]

    def preview(self) -> str:
        lines = [self.system, "", "Recent session:"]
        for event in self.recent_messages[-8:]:
            lines.append(f"- {event.role}: {event.content}")
        return "\n".join(lines).strip()


class PromptBuilder:
    def __init__(self, system: str | None = None) -> None:
        self.system = system or (
            "You are Kairos, a local-first personal AI assistant runtime. "
            "Use tools through the permission-gated router and keep user data local."
        )

    def build(self, events: list[SessionEvent]) -> PromptBundle:
        return PromptBundle(system=self.system, recent_messages=events[-20:])
