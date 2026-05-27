from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from kairos.config import KairosPaths
from kairos.memory import MemoryEntry, MemoryScope, MemoryStore, MemoryType
from kairos.tools.registry import ToolResult, ToolSpec


class WebSearchAdapter(Protocol):
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class EnvironmentWebSearchAdapter:
    """Offline-friendly search adapter for tests and local demos.

    Real providers can be added behind this contract later. The default keeps
    the tool callable without making hidden network requests.
    """

    environ: dict[str, str]
    root: Path

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        raw_results = self.environ.get("KAIROS_WEB_SEARCH_RESULTS")
        fixture_path = self.environ.get("KAIROS_WEB_SEARCH_FIXTURE")
        if raw_results:
            return _filter_results(json.loads(raw_results), query, limit)
        if fixture_path:
            path = (self.root / fixture_path).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError(f"Search fixture escapes project root: {fixture_path}")
            return _filter_results(json.loads(path.read_text(encoding="utf-8")), query, limit)
        return []


def build_advanced_tools(paths: KairosPaths) -> list[ToolSpec]:
    search_adapter = EnvironmentWebSearchAdapter(dict(os.environ), paths.root)
    return [
        ToolSpec(
            name="web.search",
            description=(
                "Search the web or a configured search fixture. Returns concise result metadata; "
                "no browser automation is launched by this MVP tool."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
            },
            risk_level="low",
            source="native",
            handler=lambda query, limit=5: _web_search(search_adapter, query, limit),
        ),
        ToolSpec(
            name="weather.current",
            description="Return current weather context from local Kairos configuration or environment.",
            input_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                },
            },
            risk_level="low",
            source="native",
            handler=lambda location="": _current_weather(location),
        ),
        ToolSpec(
            name="location.current",
            description="Return the user's configured approximate location context.",
            input_schema={"type": "object", "properties": {}},
            risk_level="low",
            source="native",
            handler=lambda: _current_location(),
        ),
        ToolSpec(
            name="memory.search",
            description="Search confirmed and candidate Kairos memories by keyword.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                    "include_candidates": {"type": "boolean"},
                },
                "required": ["query"],
            },
            risk_level="low",
            source="native",
            handler=lambda query, limit=5, include_candidates=False: _memory_search(
                paths, query, limit, include_candidates
            ),
        ),
        ToolSpec(
            name="memory.save_candidate",
            description="Save a proposed memory candidate for later user review and confirmation.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "content": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [item.value for item in MemoryType],
                    },
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["name", "description", "content"],
            },
            risk_level="low",
            source="native",
            handler=lambda name, description, content, type="user", confidence=0.6, reason="agent proposed": _save_memory_candidate(
                paths, name, description, content, type, confidence, reason
            ),
        ),
    ]


def _web_search(adapter: WebSearchAdapter, query: str, limit: int = 5) -> ToolResult:
    limit = _coerce_limit(limit)
    results = adapter.search(str(query), limit=limit)
    if not results:
        return ToolResult(
            "ok",
            "No configured search provider returned results. Set KAIROS_WEB_SEARCH_RESULTS or KAIROS_WEB_SEARCH_FIXTURE for now.",
            {"query": query, "results": [], "configured": False},
        )
    preview = "\n".join(
        f"- {item.get('title', 'Untitled')}: {item.get('url', '')}".rstrip(": ")
        for item in results
    )
    return ToolResult("ok", preview, {"query": query, "results": results, "configured": True})


def _current_weather(location: str = "") -> ToolResult:
    configured_location = location or os.environ.get("KAIROS_LOCATION_NAME", "")
    summary = os.environ.get("KAIROS_WEATHER_SUMMARY", "")
    temperature = os.environ.get("KAIROS_WEATHER_TEMPERATURE_C", "")
    condition = os.environ.get("KAIROS_WEATHER_CONDITION", "")
    data = {
        "location": configured_location or None,
        "summary": summary or None,
        "temperature_c": _optional_float(temperature),
        "condition": condition or None,
        "configured": bool(summary or temperature or condition),
    }
    if not data["configured"]:
        return ToolResult(
            "ok",
            "Weather is not configured yet. Provide KAIROS_WEATHER_SUMMARY or wire a provider adapter.",
            data,
        )
    parts = [part for part in (configured_location, condition, temperature and f"{temperature}C", summary) if part]
    return ToolResult("ok", " | ".join(parts), data)


def _current_location() -> ToolResult:
    name = os.environ.get("KAIROS_LOCATION_NAME", "")
    latitude = os.environ.get("KAIROS_LOCATION_LATITUDE", "")
    longitude = os.environ.get("KAIROS_LOCATION_LONGITUDE", "")
    data = {
        "name": name or None,
        "latitude": _optional_float(latitude),
        "longitude": _optional_float(longitude),
        "configured": bool(name or latitude or longitude),
    }
    if not data["configured"]:
        return ToolResult(
            "ok",
            "Location is not configured yet. Set KAIROS_LOCATION_NAME for local recommendations.",
            data,
        )
    preview = name or f"{latitude},{longitude}"
    return ToolResult("ok", preview, data)


def _memory_search(
    paths: KairosPaths,
    query: str,
    limit: int = 5,
    include_candidates: bool = False,
) -> ToolResult:
    limit = _coerce_limit(limit)
    needle = str(query).strip().lower()
    if not needle:
        return ToolResult("error", "query is required")
    matches: list[dict[str, Any]] = []
    for entry, path, candidate in MemoryStore(paths).list_with_paths(
        include_candidates=_truthy(include_candidates)
    ):
        haystack = " ".join([entry.name, entry.description, entry.content]).lower()
        score = haystack.count(needle)
        if score == 0 and all(token in haystack for token in needle.split()):
            score = 1
        if score == 0:
            continue
        matches.append(
            {
                "name": entry.name,
                "description": entry.description,
                "type": entry.type.value,
                "content": entry.content,
                "candidate": candidate,
                "path": str(path),
                "score": score,
            }
        )
    matches.sort(key=lambda item: (-int(item["score"]), str(item["name"])))
    matches = matches[:limit]
    if not matches:
        return ToolResult("ok", f"No memory matched: {query}", {"query": query, "matches": []})
    preview = "\n".join(f"- {item['name']}: {item['description']}" for item in matches)
    return ToolResult("ok", preview, {"query": query, "matches": matches})


def _save_memory_candidate(
    paths: KairosPaths,
    name: str,
    description: str,
    content: str,
    memory_type: str = "user",
    confidence: float = 0.6,
    reason: str = "agent proposed",
) -> ToolResult:
    entry = MemoryEntry(
        name=str(name),
        description=str(description),
        type=MemoryType(str(memory_type)),
        scope=MemoryScope.PRIVATE,
        confidence=float(confidence),
        source="agent/tool",
        candidate_reason=str(reason),
        content=str(content),
    )
    path = MemoryStore(paths).save(entry, candidate=True)
    return ToolResult(
        "ok",
        f"Saved memory candidate: {entry.name}",
        {"memory": entry.name, "candidate": True, "path": str(path)},
    )


def _filter_results(raw: object, query: str, limit: int) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raw_items = raw.get("results", [])
    else:
        raw_items = raw
    if not isinstance(raw_items, list):
        return []
    needle = query.strip().lower()
    results: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "Untitled"))
        snippet = str(item.get("snippet", item.get("content", "")))
        url = str(item.get("url", ""))
        haystack = f"{title} {snippet} {url}".lower()
        if needle and needle not in haystack and not all(token in haystack for token in needle.split()):
            continue
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


def _coerce_limit(value: object) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 5
    return max(1, min(limit, 10))


def _optional_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
