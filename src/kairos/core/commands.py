from __future__ import annotations

from dataclasses import dataclass, field
import shlex
from typing import Literal

CommandKind = Literal["tool", "help", "plain"]


@dataclass(frozen=True)
class ParsedCommand:
    kind: CommandKind
    name: str = ""
    arguments: dict[str, str] = field(default_factory=dict)
    text: str = ""


def parse_agent_command(text: str) -> ParsedCommand:
    stripped = text.strip()
    if stripped in {"/help", "help"}:
        return ParsedCommand(kind="help", text=stripped)
    if not stripped.startswith("/tool "):
        return ParsedCommand(kind="plain", text=text)

    parts = shlex.split(stripped)
    if len(parts) < 2:
        return ParsedCommand(kind="help", text=stripped)
    args: dict[str, str] = {}
    for item in parts[2:]:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        args[key] = value
    return ParsedCommand(kind="tool", name=parts[1], arguments=args, text=text)
