from __future__ import annotations

from .base import Channel


class ChannelManager:
    def __init__(self, channels: list[Channel] | None = None) -> None:
        self._channels: dict[str, Channel] = {}
        for channel in channels or []:
            self.register(channel)

    def register(self, channel: Channel) -> None:
        self._channels[channel.name] = channel

    def get(self, name: str) -> Channel | None:
        return self._channels.get(name)

    def send(self, channel: str, to: str, text: str) -> bool:
        target = self.get(channel)
        if target is None:
            return False
        return target.send(to=to, text=text)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._channels))

