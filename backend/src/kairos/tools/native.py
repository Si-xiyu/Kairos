from __future__ import annotations

from pathlib import Path
from typing import Any

from kairos.config import KairosPaths
from kairos.mcp import build_mcp_tool_specs
from kairos.tools.advanced import build_advanced_tools
from kairos.tools.registry import ToolRegistry, ToolResult, ToolSpec


def build_native_registry(paths: KairosPaths) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="file.read",
            description="Read a UTF-8 text file inside the project root.",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            risk_level="low",
            source="native",
            handler=lambda path: _read_file(paths, path),
        )
    )
    registry.register(
        ToolSpec(
            name="file.write",
            description="Write UTF-8 text to a file inside the project root.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                },
            },
            risk_level="medium",
            source="native",
            handler=lambda path, content, overwrite=False: _write_file(
                paths, path, content, overwrite=overwrite
            ),
        )
    )
    registry.register(
        ToolSpec(
            name="file.list",
            description="List files under a directory inside the project root.",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
            risk_level="low",
            source="native",
            handler=lambda path=".": _list_files(paths, path),
        )
    )
    for spec in build_advanced_tools(paths):
        registry.register(spec)
    for spec in build_mcp_tool_specs(paths):
        registry.register(spec)
    return registry


def _read_file(paths: KairosPaths, path: str) -> ToolResult:
    target = _resolve_project_path(paths, path)
    if not target.is_file():
        return ToolResult("error", f"Not a file: {target}")
    text = target.read_text(encoding="utf-8")
    return ToolResult("ok", text[:1000], {"path": str(target), "content": text})


def _write_file(paths: KairosPaths, path: str, content: str, overwrite: bool = False) -> ToolResult:
    target = _resolve_project_path(paths, path)
    if target.exists() and not overwrite:
        return ToolResult("error", f"File exists and overwrite is false: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ToolResult("ok", f"Wrote {len(content)} bytes to {target}", {"path": str(target)})


def _list_files(paths: KairosPaths, path: str = ".") -> ToolResult:
    target = _resolve_project_path(paths, path)
    if not target.exists():
        return ToolResult("error", f"Path does not exist: {target}")
    if target.is_file():
        return ToolResult("ok", target.name, {"files": [str(target)]})
    files = sorted(str(p.relative_to(paths.root)) for p in target.iterdir())
    return ToolResult("ok", "\n".join(files), {"files": files})


def _resolve_project_path(paths: KairosPaths, value: str) -> Path:
    candidate = (paths.root / value).resolve()
    if not candidate.is_relative_to(paths.root):
        raise ValueError(f"Path escapes project root: {value}")
    return candidate


def parse_tool_arguments(raw: str | None) -> dict[str, Any]:
    if raw is None or not raw.strip():
        return {}
    import json

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = json.loads(raw.replace('\\"', '"'))
    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    return parsed
