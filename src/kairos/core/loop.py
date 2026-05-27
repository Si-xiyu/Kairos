from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kairos.core.commands import parse_agent_command
from kairos.core.context import RuntimeContext
from kairos.core.context_window import ContextWindow
from kairos.core.memory_capture import capture_memory_candidates
from kairos.core.prompt import PromptBuilder
from kairos.core.session import SessionEvent
from kairos.llm import (
    ChatProvider,
    ChatProviderError,
    ModelMessage,
    ModelTool,
    ModelToolCall,
    provider_from_env,
)
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
        context_window: ContextWindow | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self.context = context
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.chat_provider = chat_provider or provider_from_env()
        self.context_window = context_window or ContextWindow()
        self.max_tool_rounds = max_tool_rounds

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
            text = self._run_model_query(observations)

        self.context.sessions.append(
            self.context.session_id,
            SessionEvent(role="assistant", content=text),
        )
        memory_events = self.context.sessions.read(self.context.session_id)
        captures = capture_memory_candidates(self.context.paths, self.context.session_id, memory_events)
        observations.extend(f"memory candidate: {capture.name}" for capture in captures)
        return AgentTurnResult(
            outbound=[OutboundMessage(channel=inbound.channel, to=inbound.peer_id, text=text)],
            observations=observations,
        )

    def _run_model_query(self, observations: list[str]) -> str:
        assert self.context is not None
        tools = _model_tools(self.context)
        for round_index in range(self.max_tool_rounds + 1):
            events = self.context.sessions.read(self.context.session_id)
            prompt = self.prompt_builder.build(events)
            context = self.context_window.build(
                system=prompt.system,
                events=prompt.recent_messages,
                provider=self.chat_provider,
                tools=tools,
            )
            observations.extend(context.observations)
            if context.summary:
                captures = capture_memory_candidates(
                    self.context.paths,
                    self.context.session_id,
                    events,
                    summary=context.summary,
                )
                observations.extend(f"memory candidate: {capture.name}" for capture in captures)

            try:
                reply = self.chat_provider.complete(
                    system=prompt.system,
                    messages=context.messages,
                    tools=tools,
                )
            except ChatProviderError as exc:
                observations.append(f"model error: {exc}")
                return (
                    "Kairos 的模型通道暂时没有跑通。\n"
                    f"错误：{exc}\n\n"
                    "你仍然可以使用 `/tool file.list path=.` 测试工具和权限管道。"
                )

            if not reply.tool_calls:
                observations.append(f"model {reply.provider}/{reply.model}: ok")
                return reply.text

            observations.append(
                f"model {reply.provider}/{reply.model}: requested {len(reply.tool_calls)} tool call(s)"
            )
            self.context.sessions.append(
                self.context.session_id,
                SessionEvent(
                    role="assistant",
                    content=reply.text or _tool_call_summary(reply.tool_calls),
                    metadata={"tool_calls": [_tool_call_to_json(call) for call in reply.tool_calls]},
                ),
            )
            for call in reply.tool_calls:
                result = self.context.tool_router.call(
                    _runtime_tool_name(self.context, call.name),
                    dict(call.arguments),
                )
                observations.append(f"tool {result.tool_name}: {result.status}")
                self.context.sessions.append(
                    self.context.session_id,
                    SessionEvent(
                        role="tool",
                        content=result.preview,
                        metadata={
                            "tool": result.tool_name,
                            "tool_call_id": call.id,
                            "status": result.status,
                            "arguments": dict(call.arguments),
                        },
                    ),
                )
            if round_index >= self.max_tool_rounds - 1:
                return "I paused after reaching the tool-call round limit. Please review the tool results."

        return "I paused because the agent loop reached its turn budget."


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


def _model_tools(context: RuntimeContext) -> list[ModelTool]:
    return [
        ModelTool(
            name=_model_tool_name(spec.name),
            description=spec.description,
            input_schema=spec.input_schema,
        )
        for spec in context.tool_router.registry.list()
    ]


def _tool_call_summary(tool_calls: tuple[ModelToolCall, ...]) -> str:
    names = ", ".join(call.name for call in tool_calls)
    return f"Tool call requested: {names}"


def _tool_call_to_json(call: ModelToolCall) -> dict[str, Any]:
    return {"id": call.id, "name": call.name, "arguments": dict(call.arguments)}


def _model_tool_name(runtime_name: str) -> str:
    return runtime_name.replace(".", "__")


def _runtime_tool_name(context: RuntimeContext, model_name: str) -> str:
    known = {spec.name for spec in context.tool_router.registry.list()}
    if model_name in known:
        return model_name
    candidate = model_name.replace("__", ".")
    if candidate in known:
        return candidate
    return model_name
