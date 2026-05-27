from __future__ import annotations

from dataclasses import dataclass, field

from kairos.core.commands import parse_agent_command
from kairos.core.context import RuntimeContext
from kairos.core.prompt import PromptBuilder
from kairos.core.session import SessionEvent
from kairos.llm import ChatProvider, ChatProviderError, ModelMessage, provider_from_env
from kairos.messages import InboundMessage, OutboundMessage


@dataclass(frozen=True)
class AgentTurnResult:
    outbound: list[OutboundMessage] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)


class AgentLoop:
    """Single-agent query loop.

    Slash commands still exercise the deterministic tool path. Plain messages
    now flow through a chat provider so the same API endpoint can host real
    conversation before model-driven tool calls are added.
    """

    def __init__(
        self,
        context: RuntimeContext | None = None,
        prompt_builder: PromptBuilder | None = None,
        chat_provider: ChatProvider | None = None,
    ) -> None:
        self.context = context
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.chat_provider = chat_provider or provider_from_env()

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
            try:
                reply = self.chat_provider.complete(
                    system=prompt.system,
                    messages=_model_messages(prompt.recent_messages),
                )
                text = reply.text
                observations.append(f"model {reply.provider}/{reply.model}: ok")
            except ChatProviderError as exc:
                text = (
                    "Kairos 的模型通道暂时没有跑通。\n"
                    f"错误：{exc}\n\n"
                    "你仍然可以使用 `/tool file.list path=.` 测试工具和权限管道。"
                )
                observations.append(f"model error: {exc}")

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


def _model_messages(events: list[SessionEvent]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for event in events:
        if event.role in {"user", "assistant"}:
            messages.append(ModelMessage(role=event.role, content=event.content))
        elif event.role == "tool":
            tool_name = event.metadata.get("tool", "tool")
            messages.append(
                ModelMessage(
                    role="user",
                    content=f"Tool result from {tool_name}:\n{event.content}",
                )
            )
    return messages
