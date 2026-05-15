from __future__ import annotations

from dataclasses import dataclass, field

from kairos.core.commands import parse_agent_command
from kairos.core.context import RuntimeContext
from kairos.core.prompt import PromptBuilder
from kairos.core.session import SessionEvent
from kairos.messages import InboundMessage, OutboundMessage


@dataclass(frozen=True)
class AgentTurnResult:
    outbound: list[OutboundMessage] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)


class AgentLoop:
    """Deterministic runtime loop scaffold.

    This does not call an LLM yet. It provides the same session/tool/permission
    path that the future model loop will use.
    """

    def __init__(
        self,
        context: RuntimeContext | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.context = context
        self.prompt_builder = prompt_builder or PromptBuilder()

    def run_turn(self, inbound: InboundMessage) -> AgentTurnResult:
        if self.context is None:
            text = "`AgentLoop` needs a RuntimeContext for executable turns."
            return _single_outbound(inbound, text)

        self.context.sessions.append(
            self.context.session_id,
            SessionEvent(
                role="user",
                content=inbound.text,
                metadata={"channel": inbound.channel, "peer_id": inbound.peer_id},
            ),
        )
        command = parse_agent_command(inbound.text)
        observations: list[str] = []

        if command.kind == "help":
            text = _help_text()
        elif command.kind == "tool":
            result = self.context.tool_router.call(command.name, command.arguments)
            observations.append(result.preview)
            text = f"tool {result.tool_name}: {result.status}"
            if result.preview:
                text += f"\n{result.preview}"
            self.context.sessions.append(
                self.context.session_id,
                SessionEvent(
                    role="tool",
                    content=result.preview,
                    metadata={"tool": result.tool_name, "status": result.status},
                ),
            )
        else:
            events = self.context.sessions.read(self.context.session_id)
            prompt = self.prompt_builder.build(events)
            text = (
                "Kairos runtime is ready. LLM integration is not wired yet.\n"
                "Try `/tool file.list path=.` to exercise the tool router.\n\n"
                f"Prompt preview:\n{prompt.preview()}"
            )

        self.context.sessions.append(
            self.context.session_id,
            SessionEvent(role="assistant", content=text),
        )
        return AgentTurnResult(
            outbound=[OutboundMessage(channel=inbound.channel, to=inbound.peer_id, text=text)],
            observations=observations,
        )


def _single_outbound(inbound: InboundMessage, text: str) -> AgentTurnResult:
    return AgentTurnResult(
        outbound=[OutboundMessage(channel=inbound.channel, to=inbound.peer_id, text=text)]
    )


def _help_text() -> str:
    return "\n".join(
        [
            "Kairos runtime commands:",
            "- /help",
            "- /tool file.list path=.",
            "- /tool file.read path=README.md",
        ]
    )
