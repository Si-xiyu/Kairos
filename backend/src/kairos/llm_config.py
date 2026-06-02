from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

LLM_ENV_KEYS = {
    "provider": "KAIROS_LLM_PROVIDER",
    "base_url": "KAIROS_LLM_BASE_URL",
    "api_key": "KAIROS_LLM_API_KEY",
    "model": "KAIROS_LLM_MODEL",
    "timeout": "KAIROS_LLM_TIMEOUT",
}


def load_llm_environment(
    root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Merge LLM settings from JSON, .env, and process environment.

    Precedence is:

    1. process environment / explicit environ mapping
    2. .env file values
    3. JSON config values
    4. provider defaults in the LLM provider layer
    """

    root = (root or Path.cwd()).resolve()
    merged: dict[str, str] = {}
    merged.update(_json_llm_environment(root))
    merged.update(_dotenv_environment(root))
    merged.update(dict(os.environ if environ is None else environ))
    return merged


def _json_llm_environment(root: Path) -> dict[str, str]:
    for path in _json_config_paths(root):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("llm"), dict):
            data = data["llm"]
        values: dict[str, str] = {}
        for json_key, env_key in LLM_ENV_KEYS.items():
            if json_key in data and data[json_key] is not None:
                values[env_key] = str(data[json_key])
        return values
    return {}


def _dotenv_environment(root: Path) -> dict[str, str]:
    path = root / ".env"
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        values[key] = _unquote_env_value(value)
    return values


def _json_config_paths(root: Path) -> list[Path]:
    return [
        root / ".kairos" / "llm.json",
        root / "kairos.llm.json",
        root / "llm.json",
    ]


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
