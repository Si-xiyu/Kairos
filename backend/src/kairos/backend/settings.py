from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any

from kairos.config import KairosPaths
from kairos.llm_config import load_llm_environment


DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"


@dataclass(frozen=True)
class NotificationPolicy:
    enabled: bool = True
    high_level_enabled: bool = True
    companion_nudges_enabled: bool = True
    quiet_hours_start: str = "23:00"
    quiet_hours_end: str = "08:00"
    daily_notification_budget: int = 3
    default_channel: str = "windows_toast"


@dataclass(frozen=True)
class SettingsState:
    llm: dict[str, Any]
    storage: dict[str, Any]
    notifications: dict[str, Any] = field(default_factory=lambda: asdict(NotificationPolicy()))


class SettingsStore:
    def __init__(self, paths: KairosPaths) -> None:
        self.paths = paths
        self.path = paths.home / "settings.json"

    def read(self) -> dict[str, Any]:
        data = self._load()
        env = load_llm_environment(root=self.paths.root)
        llm = _safe_llm_settings(data.get("llm", {}), env)
        storage = {
            "kairos_home": str(self.paths.home),
            "journal_path": str(data.get("storage", {}).get("journal_path") or self.paths.journal),
            "record_path": str(data.get("storage", {}).get("record_path") or self.paths.journal / "artifacts"),
        }
        notifications = asdict(NotificationPolicy()) | dict(data.get("notifications", {}))
        return {
            "llm": llm,
            "storage": storage,
            "notifications": notifications,
            "memory_review": {
                "available": True,
                "href": "/api/memories?include_candidates=true",
            },
            "project_scopes": {
                "available": True,
                "href": "/api/project-scopes",
            },
        }

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        current = self._load()
        if isinstance(values.get("llm"), dict):
            current["llm"] = _merge_llm_for_storage(current.get("llm", {}), values["llm"])
            self._save_llm_config(current["llm"])
        if isinstance(values.get("storage"), dict):
            storage = dict(current.get("storage", {}))
            for key in ("journal_path", "record_path"):
                if key in values["storage"]:
                    storage[key] = str(values["storage"][key])
            current["storage"] = storage
        if isinstance(values.get("notifications"), dict):
            notifications = asdict(NotificationPolicy()) | dict(current.get("notifications", {}))
            notifications.update(values["notifications"])
            current["notifications"] = notifications
        self._save(current)
        return self.read()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _save_llm_config(self, llm: dict[str, Any]) -> None:
        data: dict[str, Any] = {}
        for key in ("provider", "base_url", "api_key", "model", "timeout"):
            if key in llm and llm[key] not in {None, ""}:
                data[key] = llm[key]
        target = self.paths.home / "llm.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"llm": data}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_llm_settings(stored: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    provider = str(env.get("KAIROS_LLM_PROVIDER") or stored.get("provider") or "local")
    configured_key = bool(env.get("KAIROS_LLM_API_KEY") or env.get("OPENAI_API_KEY") or stored.get("api_key"))
    if provider in {"openai-compatible", "openai", "api", "deepseek"}:
        provider = "openai-compatible"
    return {
        "provider": provider,
        "suggested_provider": "deepseek",
        "base_url": env.get("KAIROS_LLM_BASE_URL") or env.get("OPENAI_BASE_URL") or stored.get("base_url") or (DEEPSEEK_BASE_URL if provider == "openai-compatible" else None),
        "model": env.get("KAIROS_LLM_MODEL") or stored.get("model") or (DEEPSEEK_MODEL if provider == "openai-compatible" else "kairos-local-mvp"),
        "timeout": int(env.get("KAIROS_LLM_TIMEOUT") or stored.get("timeout") or 60),
        "api_key_configured": configured_key,
        "api_key_preview": "configured" if configured_key else None,
    }


def _merge_llm_for_storage(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key in ("provider", "base_url", "model", "timeout"):
        if key in update:
            merged[key] = update[key]
    if "api_key" in update and str(update["api_key"]):
        merged["api_key"] = str(update["api_key"])
    return merged
