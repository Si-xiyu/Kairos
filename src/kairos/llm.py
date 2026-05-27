from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Mapping, Protocol
from urllib import request
from urllib.error import HTTPError, URLError


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ModelReply:
    text: str
    provider: str
    model: str


class ChatProvider(Protocol):
    name: str
    model: str

    def complete(self, system: str, messages: list[ModelMessage]) -> ModelReply:
        ...


class ChatProviderError(RuntimeError):
    pass


class LocalCompanionProvider:
    name = "local"
    model = "kairos-local-mvp"

    def complete(self, system: str, messages: list[ModelMessage]) -> ModelReply:
        last_user = next((message.content for message in reversed(messages) if message.role == "user"), "")
        if not last_user.strip():
            text = "我在。你可以直接和我说接下来要推进什么。"
        else:
            text = (
                "我在，先用本地 MVP 模式陪你把对话跑通。\n\n"
                f"我听到的是：{last_user.strip()}\n\n"
                "如果你配置 `KAIROS_LLM_PROVIDER=openai-compatible`，这条通道会切到真实模型。"
            )
        return ModelReply(text=text, provider=self.name, model=self.model)


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def complete(self, system: str, messages: list[ModelMessage]) -> ModelReply:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                *[
                    {"role": message.role, "content": message.content}
                    for message in messages
                    if message.content.strip()
                ],
            ],
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ChatProviderError(f"model provider HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise ChatProviderError(f"model provider connection failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ChatProviderError("model provider request timed out") from exc

        parsed = json.loads(raw)
        try:
            text = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatProviderError(f"unexpected model provider response: {raw[:500]}") from exc
        return ModelReply(text=str(text), provider=self.name, model=self.model)


def provider_from_env(environ: Mapping[str, str] | None = None) -> ChatProvider:
    environ = environ or os.environ
    provider = environ.get("KAIROS_LLM_PROVIDER", "local").strip().lower()
    if provider in {"", "local", "mock", "fallback"}:
        return LocalCompanionProvider()
    if provider in {"openai", "openai-compatible", "api"}:
        return OpenAICompatibleProvider(
            base_url=environ.get("KAIROS_LLM_BASE_URL")
            or environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1",
            model=environ.get("KAIROS_LLM_MODEL")
            or environ.get("MODEL_ID")
            or "gpt-4.1-mini",
            api_key=environ.get("KAIROS_LLM_API_KEY") or environ.get("OPENAI_API_KEY"),
            timeout_seconds=int(environ.get("KAIROS_LLM_TIMEOUT", "60")),
        )
    raise ChatProviderError(f"unsupported KAIROS_LLM_PROVIDER: {provider}")
