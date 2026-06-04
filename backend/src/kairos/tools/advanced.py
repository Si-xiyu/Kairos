from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib import parse, request
from urllib.error import HTTPError, URLError

from kairos.config import KairosPaths
from kairos.backend.todos import TodoStore, proposed_todo
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
        return HttpWebSearchAdapter(self.environ).search(query, limit)


@dataclass(frozen=True)
class HttpWebSearchAdapter:
    environ: dict[str, str]

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        provider = self.environ.get("KAIROS_WEB_SEARCH_PROVIDER", "").strip().lower()
        if provider == "brave":
            return self._brave(query, limit)
        if provider == "tavily":
            return self._tavily(query, limit)
        if self.environ.get("KAIROS_WEB_SEARCH_URL"):
            return self._generic(query, limit)
        return []

    def _brave(self, query: str, limit: int) -> list[dict[str, Any]]:
        token = self.environ.get("KAIROS_BRAVE_SEARCH_API_KEY") or self.environ.get("BRAVE_SEARCH_API_KEY")
        if not token:
            return []
        url = "https://api.search.brave.com/res/v1/web/search?" + parse.urlencode(
            {"q": query, "count": limit}
        )
        data = _http_json("GET", url, headers={"X-Subscription-Token": token})
        raw_results = ((data.get("web") or {}).get("results") if isinstance(data, dict) else []) or []
        return _normalize_search_results(raw_results, limit)

    def _tavily(self, query: str, limit: int) -> list[dict[str, Any]]:
        token = self.environ.get("KAIROS_TAVILY_API_KEY") or self.environ.get("TAVILY_API_KEY")
        if not token:
            return []
        data = _http_json(
            "POST",
            "https://api.tavily.com/search",
            payload={"api_key": token, "query": query, "max_results": limit},
        )
        raw_results = data.get("results", []) if isinstance(data, dict) else []
        return _normalize_search_results(raw_results, limit)

    def _generic(self, query: str, limit: int) -> list[dict[str, Any]]:
        template = self.environ["KAIROS_WEB_SEARCH_URL"]
        url = template.format(
            query=parse.quote(query),
            query_plus=parse.quote_plus(query),
            limit=limit,
        )
        header_name = self.environ.get("KAIROS_WEB_SEARCH_HEADER_NAME")
        header_value = self.environ.get("KAIROS_WEB_SEARCH_HEADER_VALUE")
        headers = {header_name: header_value} if header_name and header_value else {}
        data = _http_json("GET", url, headers=headers)
        raw_results = data.get("results", data) if isinstance(data, dict) else data
        return _normalize_search_results(raw_results, limit)


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
        ToolSpec(
            name="todo.propose",
            description="Prepare a proposed Todo for user confirmation without saving it.",
            input_schema=_todo_schema(required=["title"]),
            risk_level="low",
            source="native",
            handler=lambda **kwargs: _todo_propose(kwargs),
        ),
        ToolSpec(
            name="todo.create",
            description="Create a reliable Todo or reminder after permission approval.",
            input_schema=_todo_schema(required=["title"]),
            risk_level="medium",
            source="native",
            handler=lambda **kwargs: _todo_create(paths, kwargs),
        ),
        ToolSpec(
            name="todo.update",
            description="Update an existing Todo after permission approval.",
            input_schema=_todo_schema(required=["id"]),
            risk_level="medium",
            source="native",
            handler=lambda **kwargs: _todo_update(paths, kwargs),
        ),
        ToolSpec(
            name="todo.complete",
            description="Mark an existing Todo completed after permission approval.",
            input_schema={"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
            risk_level="medium",
            source="native",
            handler=lambda id: _todo_complete(paths, id),
        ),
        ToolSpec(
            name="todo.delete",
            description="Delete an existing Todo after permission approval.",
            input_schema={"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
            risk_level="medium",
            source="native",
            handler=lambda id: _todo_delete(paths, id),
        ),
        ToolSpec(
            name="meal.recommend",
            description=(
                "Recommend what the user should eat for a meal by combining configured "
                "location, weather, and confirmed preference memories. Use this for "
                "questions like 'what should I eat for lunch today?'."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "meal_time": {"type": "string", "default": "lunch"},
                    "location": {"type": "string"},
                    "budget": {"type": "string"},
                    "include_candidates": {"type": "boolean"},
                },
            },
            risk_level="low",
            source="native",
            handler=lambda meal_time="lunch", location="", budget="", include_candidates=False: _meal_recommend(
                paths, meal_time, location, budget, include_candidates
            ),
        ),
    ]


def _web_search(adapter: WebSearchAdapter, query: str, limit: int = 5) -> ToolResult:
    limit = _coerce_limit(limit)
    results = adapter.search(str(query), limit=limit)
    if not results:
        return ToolResult(
            "ok",
            (
                "No configured search provider returned results. Configure "
                "KAIROS_WEB_SEARCH_PROVIDER=brave|tavily, KAIROS_WEB_SEARCH_URL, "
                "or a local fixture."
            ),
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


def _todo_schema(required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "notes": {"type": "string"},
            "kind": {"type": "string", "enum": ["event", "task", "reminder"]},
            "list_id": {"type": "string"},
            "status": {"type": "string", "enum": ["open", "completed"]},
            "due_at": {"type": "string"},
            "remind_at": {"type": "string"},
            "reminder_level": {"type": "string", "enum": ["high", "normal", "none"]},
            "source": {"type": "string", "enum": ["manual", "kairos", "chat"]},
            "source_ref": {"type": "string"},
        },
        "required": required,
    }


def _todo_propose(values: dict[str, Any]) -> ToolResult:
    proposal = proposed_todo({**values, "source": values.get("source", "kairos")})
    todo = proposal["todo"]
    return ToolResult(
        "ok",
        f"Proposed todo: {todo['title']}",
        proposal,
    )


def _todo_create(paths: KairosPaths, values: dict[str, Any]) -> ToolResult:
    todo = TodoStore(paths).create_todo({**values, "source": values.get("source", "kairos")})
    return ToolResult("ok", f"Created todo: {todo['title']}", {"todo": todo})


def _todo_update(paths: KairosPaths, values: dict[str, Any]) -> ToolResult:
    todo_id = str(values.pop("id"))
    todo = TodoStore(paths).update_todo(todo_id, values)
    return ToolResult("ok", f"Updated todo: {todo['title']}", {"todo": todo})


def _todo_complete(paths: KairosPaths, todo_id: str) -> ToolResult:
    todo = TodoStore(paths).complete_todo(str(todo_id))
    return ToolResult("ok", f"Completed todo: {todo['title']}", {"todo": todo})


def _todo_delete(paths: KairosPaths, todo_id: str) -> ToolResult:
    deleted = TodoStore(paths).delete_todo(str(todo_id))
    status = "ok" if deleted else "error"
    preview = f"Deleted todo: {todo_id}" if deleted else f"Todo not found: {todo_id}"
    return ToolResult(status, preview, {"deleted": deleted})


def _meal_recommend(
    paths: KairosPaths,
    meal_time: str = "lunch",
    location: str = "",
    budget: str = "",
    include_candidates: bool = False,
) -> ToolResult:
    location_result = _current_location()
    weather_result = _current_weather(location or str(location_result.data.get("name") or ""))
    preferences = _food_preferences(paths, include_candidates=_truthy(include_candidates))
    weather = weather_result.data
    recommendation = _choose_meal(weather, preferences)
    rationale = _meal_rationale(weather, preferences, budget)
    configured = {
        "location": bool(location_result.data.get("configured") or location),
        "weather": bool(weather_result.data.get("configured")),
        "memory": bool(preferences),
    }
    data = {
        "meal_time": meal_time or "lunch",
        "location": location or location_result.data.get("name"),
        "budget": budget or None,
        "weather": weather,
        "preferences": preferences,
        "recommendation": recommendation,
        "alternatives": _meal_alternatives(recommendation, weather),
        "rationale": rationale,
        "configured": configured,
    }
    preview = (
        f"Recommend {recommendation['primary']} for {data['meal_time']}. "
        f"Reason: {'; '.join(rationale)}"
    )
    return ToolResult("ok", preview, data)


def _food_preferences(paths: KairosPaths, include_candidates: bool = False) -> list[dict[str, Any]]:
    if not paths.memory.exists():
        return []
    keywords = {
        "food",
        "meal",
        "lunch",
        "dinner",
        "breakfast",
        "eat",
        "noodle",
        "rice",
        "soup",
        "spicy",
        "vegetarian",
        "coffee",
        "restaurant",
    }
    matches: list[dict[str, Any]] = []
    for entry, _path, candidate in MemoryStore(paths).list_with_paths(
        include_candidates=include_candidates
    ):
        text = " ".join([entry.name, entry.description, entry.content]).lower()
        if not any(keyword in text for keyword in keywords):
            continue
        matches.append(
            {
                "name": entry.name,
                "description": entry.description,
                "content": entry.content,
                "candidate": candidate,
            }
        )
    return matches[:5]


def _choose_meal(
    weather: dict[str, Any],
    preferences: list[dict[str, Any]],
) -> dict[str, str]:
    text = " ".join(
        [
            str(weather.get("summary") or ""),
            str(weather.get("condition") or ""),
            *[str(item.get("content") or "") for item in preferences],
            *[str(item.get("description") or "") for item in preferences],
        ]
    ).lower()
    temperature = weather.get("temperature_c")
    if "vegetarian" in text:
        return {"primary": "a warm vegetarian rice bowl", "style": "vegetarian"}
    if "spicy" in text:
        return {"primary": "spicy noodles with a light side", "style": "spicy"}
    if "rain" in text or "cold" in text or (isinstance(temperature, float) and temperature <= 12):
        return {"primary": "hot soup noodles", "style": "warm"}
    if "hot" in text or (isinstance(temperature, float) and temperature >= 28):
        return {"primary": "cold noodles or a light rice bowl", "style": "light"}
    if "rice" in text:
        return {"primary": "a balanced rice bowl", "style": "balanced"}
    return {"primary": "a warm noodle bowl with vegetables and protein", "style": "balanced"}


def _meal_alternatives(recommendation: dict[str, str], weather: dict[str, Any]) -> list[str]:
    style = recommendation.get("style")
    if style == "spicy":
        return ["mala tang with vegetables", "spicy beef noodles"]
    if style == "vegetarian":
        return ["vegetarian curry rice", "mushroom noodle soup"]
    if style == "light":
        return ["cold soba", "chicken salad rice bowl"]
    if style == "warm":
        return ["wonton soup", "tomato beef noodles"]
    if weather.get("configured"):
        return ["rice bowl", "noodle soup"]
    return ["rice bowl", "noodle soup", "nearby set lunch"]


def _meal_rationale(
    weather: dict[str, Any],
    preferences: list[dict[str, Any]],
    budget: str,
) -> list[str]:
    rationale: list[str] = []
    if weather.get("configured"):
        summary = weather.get("summary") or weather.get("condition") or "configured weather"
        rationale.append(f"weather context: {summary}")
    else:
        rationale.append("weather provider is not configured, so the recommendation stays conservative")
    if preferences:
        rationale.append(f"matched {len(preferences)} food-related memory item(s)")
    else:
        rationale.append("no confirmed food preference memory was found")
    if budget:
        rationale.append(f"budget preference: {budget}")
    return rationale


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


def _normalize_search_results(raw: object, limit: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    results: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or item.get("heading") or "Untitled")
        url = str(item.get("url") or item.get("link") or item.get("href") or "")
        snippet = str(item.get("snippet") or item.get("description") or item.get("content") or "")
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


def _http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> object:
    headers = {"Accept": "application/json", **(headers or {})}
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"web search HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"web search connection failed: {exc.reason}") from exc
    return json.loads(raw)


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
