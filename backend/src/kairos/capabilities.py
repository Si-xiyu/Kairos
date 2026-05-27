from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from kairos.config import KairosPaths
from kairos.memory.model import parse_frontmatter
from kairos.tools.native import build_native_registry


@dataclass(frozen=True)
class SkillDocument:
    name: str
    description: str
    path: Path
    body: str

    def manifest(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "path": str(self.path),
        }


class SkillRegistry:
    """Lightweight skill discovery with on-demand body loading."""

    def __init__(self, paths: KairosPaths) -> None:
        self.paths = paths

    def list(self) -> list[SkillDocument]:
        skills: list[SkillDocument] = []
        seen: set[str] = set()
        for root in self._roots():
            if not root.exists():
                continue
            for path in sorted(root.rglob("SKILL.md")):
                skill = self._read_skill(path)
                if skill.name in seen:
                    continue
                seen.add(skill.name)
                skills.append(skill)
        return skills

    def load(self, name: str) -> SkillDocument:
        for skill in self.list():
            if skill.name == name:
                return skill
        raise FileNotFoundError(f"Skill not found: {name}")

    def _roots(self) -> list[Path]:
        return [
            self.paths.root / "skills",
            self.paths.home / "skills",
        ]

    def _read_skill(self, path: Path) -> SkillDocument:
        raw = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(raw)
        name = metadata.get("name") or path.parent.name
        description = metadata.get("description") or _first_non_heading_line(body)
        return SkillDocument(
            name=name,
            description=description,
            path=path,
            body=body.strip(),
        )


def list_capabilities(paths: KairosPaths) -> dict[str, Any]:
    registry = build_native_registry(paths)
    tools = [
        {
            "name": spec.name,
            "description": spec.description,
            "risk_level": spec.risk_level,
            "source": spec.source,
            "input_schema": spec.input_schema,
        }
        for spec in registry.list()
    ]
    return {
        "tools": tools,
        "skills": [skill.manifest() for skill in SkillRegistry(paths).list()],
        "mcp_plugins": _discover_plugin_manifests(paths),
        "integration_notes": [
            "Skills are discovered as lightweight manifests and loaded on demand.",
            "MCP/plugin manifests are discovered but not connected to live transports yet.",
            "All native and future MCP tools must pass through the shared permission router.",
        ],
    }


def _discover_plugin_manifests(paths: KairosPaths) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    for path in _plugin_manifest_paths(paths):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifests.append(
            {
                "name": str(data.get("name", path.parent.name)),
                "version": str(data.get("version", "")),
                "path": str(path),
                "mcp_servers": sorted((data.get("mcpServers") or {}).keys()),
                "status": "discovered",
            }
        )
    return manifests


def _plugin_manifest_paths(paths: KairosPaths) -> list[Path]:
    candidates = [
        paths.root / ".claude-plugin" / "plugin.json",
    ]
    candidates.extend((paths.root / ".agents" / "plugins").glob("*/plugin.json"))
    candidates.extend((paths.home / "plugins").glob("*/plugin.json"))
    return [path for path in candidates if path.exists()]


def _first_non_heading_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            return stripped
    return ""
