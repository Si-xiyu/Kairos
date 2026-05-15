from __future__ import annotations

from dataclasses import dataclass, field

from kairos.messages import InboundMessage, OutboundMessage


@dataclass(frozen=True)
class AgentTurnResult:
    outbound: list[OutboundMessage] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)


class AgentLoop:
    """Minimal placeholder for the future model/tool loop."""

    def run_turn(self, inbound: InboundMessage) -> AgentTurnResult:
        text = "`AgentLoop` is not implemented yet. Runtime contracts are ready."
        return AgentTurnResult(
            outbound=[
                OutboundMessage(channel=inbound.channel, to=inbound.peer_id, text=text)
            ]
        )
