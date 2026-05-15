from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InboundMessage:
    text: str
    sender_id: str
    channel: str = "cli"
    account_id: str = "local"
    peer_id: str = "local-user"
    is_group: bool = False
    media: list[Any] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundMessage:
    channel: str
    to: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
