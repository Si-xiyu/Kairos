from __future__ import annotations

from dataclasses import dataclass, field
import json

from kairos.core.session import SessionEvent
from kairos.llm import ChatProvider, ChatProviderError, ModelMessage, ModelTool, ModelToolCall


@dataclass(frozen=True)
class ContextPolicy:
    tool_placeholder_after_chars: int = 240
    summarize_after_chars: int = 18_000
    preserve_recent_messages: int = 12


@dataclass(frozen=True)
class ContextBuildResult:
    messages: list[ModelMessage]
    observations: list[str] = field(default_factory=list)
    summary: str | None = None


class ContextWindow:
    """Builds the model-visible context from persisted session events."""

    def __init__(self, policy: ContextPolicy | None = None) -> None:
        self.policy = policy or ContextPolicy()

    def build(
        self,
        system: str,
        events: list[SessionEvent],
        provider: ChatProvider,
        tools: list[ModelTool] | None = None,
    ) -> ContextBuildResult:
        messages = [_event_to_message(event, self.policy) for event in events]
        messages = [message for message in messages if message is not None]
        observations: list[str] = []
        level1_count = sum(
            1
            for event in events
            if event.role == "tool" and len(event.content) > self.policy.tool_placeholder_after_chars
        )
        if level1_count:
            observations.append(f"context compact level1 tool placeholders: {level1_count}")

        if _context_size(messages) <= self.policy.summarize_after_chars:
            return ContextBuildResult(messages=messages, observations=observations)

        older = messages[: -self.policy.preserve_recent_messages]
        recent = messages[-self.policy.preserve_recent_messages :]
        summary = _fallback_summary(older)
        try:
            reply = provider.complete(
                system=(
                    "Summarize this conversation context for a coding and personal assistant. "
                    "Preserve user goals, decisions, useful facts, tool findings, and unresolved next steps."
                ),
                messages=[ModelMessage(role="user", content=_serialize_messages(older))],
                tools=tools or [],
            )
            if reply.text.strip():
                summary = reply.text.strip()
        except ChatProviderError as exc:
            observations.append(f"context compact level2 failed: {exc}")

        observations.append("context compact level2 summary inserted")
        return ContextBuildResult(
            messages=[
                ModelMessage(
                    role="user",
                    content=(
                        "Earlier context summary inserted by Kairos context compression:\n\n"
                        f"{summary}"
                    ),
                ),
                *recent,
            ],
            observations=observations,
            summary=summary,
        )


def _event_to_message(event: SessionEvent, policy: ContextPolicy) -> ModelMessage | None:
    if event.role in {"user", "assistant"}:
        return ModelMessage(
            role=event.role,
            content=event.content,
            tool_calls=_metadata_tool_calls(event.metadata.get("tool_calls", ())),
        )
    if event.role == "tool":
        content = event.content
        if len(content) > policy.tool_placeholder_after_chars:
            tool_name = event.metadata.get("tool", "tool")
            status = event.metadata.get("status", "ok")
            content = (
                f"[Tool result compacted: {tool_name}, status={status}, "
                f"{len(event.content)} chars. Full result is stored in the session log.]"
            )
        return ModelMessage(
            role="tool",
            content=content,
            tool_call_id=str(event.metadata.get("tool_call_id") or event.metadata.get("tool") or "tool_call"),
            name=str(event.metadata.get("tool", "tool")),
        )
    return None


def _context_size(messages: list[ModelMessage]) -> int:
    return sum(len(message.content) for message in messages)


def _serialize_messages(messages: list[ModelMessage]) -> str:
    return json.dumps(
        [
            {
                "role": message.role,
                "content": message.content,
                "name": message.name,
                "tool_call_id": message.tool_call_id,
            }
            for message in messages
        ],
        ensure_ascii=False,
        indent=2,
    )


def _fallback_summary(messages: list[ModelMessage]) -> str:
    lines = []
    for message in messages[-20:]:
        content = " ".join(message.content.split())
        if len(content) > 180:
            content = content[:177].rstrip() + "..."
        lines.append(f"- {message.role}: {content}")
    return "\n".join(lines) or "No earlier context."


def _metadata_tool_calls(raw_calls: object) -> tuple[ModelToolCall, ...]:
    if not isinstance(raw_calls, list):
        return ()
    calls: list[ModelToolCall] = []
    for raw in raw_calls:
        if not isinstance(raw, dict):
            continue
        arguments = raw.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}
        calls.append(
            ModelToolCall(
                id=str(raw.get("id") or f"tool_call_{len(calls) + 1}"),
                name=str(raw.get("name") or ""),
                arguments=arguments,
            )
        )
    return tuple(call for call in calls if call.name)
