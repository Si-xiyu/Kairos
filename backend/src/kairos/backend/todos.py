from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Literal
from uuid import uuid4

from kairos.config import KairosPaths

TodoKind = Literal["event", "task", "reminder"]
TodoStatus = Literal["open", "completed"]
ReminderLevel = Literal["high", "normal", "none"]
TodoSource = Literal["manual", "kairos", "chat"]

DEFAULT_LIST_ID = "inbox"


@dataclass(frozen=True)
class TodoList:
    id: str
    name: str
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class Todo:
    id: str
    title: str
    notes: str = ""
    kind: TodoKind = "task"
    list_id: str = DEFAULT_LIST_ID
    status: TodoStatus = "open"
    due_at: str | None = None
    remind_at: str | None = None
    reminder_level: ReminderLevel = "normal"
    source: TodoSource = "manual"
    source_ref: str | None = None
    reminder_delivery_id: str | None = None
    reminder_delivered_at: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


class TodoStore:
    def __init__(self, paths: KairosPaths) -> None:
        self.paths = paths
        self.path = paths.tasks / "todos.json"

    def snapshot(self) -> dict[str, Any]:
        data = self._load()
        return {
            "todos": sorted(data["todos"], key=_todo_sort_key),
            "lists": sorted(data["lists"], key=lambda item: item["created_at"]),
        }

    def list_todos(self, status: str | None = None, list_id: str | None = None) -> list[dict[str, Any]]:
        todos = self.snapshot()["todos"]
        if status:
            todos = [todo for todo in todos if todo["status"] == status]
        if list_id:
            todos = [todo for todo in todos if todo["list_id"] == list_id]
        return todos

    def list_lists(self) -> list[dict[str, Any]]:
        return self.snapshot()["lists"]

    def create_todo(self, values: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        now = _now()
        todo = Todo(
            id=str(values.get("id") or _new_id("todo")),
            title=_required_text(values, "title"),
            notes=str(values.get("notes", "")),
            kind=_literal(values.get("kind", "task"), {"event", "task", "reminder"}, "kind"),
            list_id=str(values.get("list_id") or DEFAULT_LIST_ID),
            status=_literal(values.get("status", "open"), {"open", "completed"}, "status"),
            due_at=_optional_iso(values.get("due_at")),
            remind_at=_optional_iso(values.get("remind_at")),
            reminder_level=_literal(
                values.get("reminder_level", "normal"),
                {"high", "normal", "none"},
                "reminder_level",
            ),
            source=_literal(values.get("source", "manual"), {"manual", "kairos", "chat"}, "source"),
            source_ref=_optional_str(values.get("source_ref")),
            reminder_delivery_id=_optional_str(values.get("reminder_delivery_id")),
            reminder_delivered_at=_optional_iso(values.get("reminder_delivered_at")),
            created_at=now,
            updated_at=now,
        )
        if any(item["id"] == todo.id for item in data["todos"]):
            raise ValueError(f"Todo already exists: {todo.id}")
        self._ensure_list(data, todo.list_id)
        data["todos"].append(asdict(todo))
        self._save(data)
        return asdict(todo)

    def update_todo(self, todo_id: str, values: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        todo = self._find_todo(data, todo_id)
        updated = {**todo}
        for key in (
            "title",
            "notes",
            "kind",
            "list_id",
            "status",
            "due_at",
            "remind_at",
            "reminder_level",
            "source",
            "source_ref",
            "reminder_delivery_id",
            "reminder_delivered_at",
        ):
            if key in values:
                updated[key] = values[key]
        updated["title"] = _required_text(updated, "title")
        updated["kind"] = _literal(updated.get("kind", "task"), {"event", "task", "reminder"}, "kind")
        updated["status"] = _literal(updated.get("status", "open"), {"open", "completed"}, "status")
        updated["reminder_level"] = _literal(
            updated.get("reminder_level", "normal"),
            {"high", "normal", "none"},
            "reminder_level",
        )
        updated["source"] = _literal(updated.get("source", "manual"), {"manual", "kairos", "chat"}, "source")
        updated["due_at"] = _optional_iso(updated.get("due_at"))
        updated["remind_at"] = _optional_iso(updated.get("remind_at"))
        updated["source_ref"] = _optional_str(updated.get("source_ref"))
        updated["reminder_delivery_id"] = _optional_str(updated.get("reminder_delivery_id"))
        updated["reminder_delivered_at"] = _optional_iso(updated.get("reminder_delivered_at"))
        updated["updated_at"] = _now()
        self._ensure_list(data, str(updated["list_id"]))
        todo.update(updated)
        self._save(data)
        return todo

    def complete_todo(self, todo_id: str) -> dict[str, Any]:
        return self.update_todo(todo_id, {"status": "completed"})

    def delete_todo(self, todo_id: str) -> bool:
        data = self._load()
        original = len(data["todos"])
        data["todos"] = [todo for todo in data["todos"] if todo["id"] != todo_id]
        deleted = len(data["todos"]) != original
        if deleted:
            self._save(data)
        return deleted

    def create_list(self, values: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        now = _now()
        item = TodoList(
            id=str(values.get("id") or _slug(_required_text(values, "name")) or _new_id("list")),
            name=_required_text(values, "name"),
            created_at=now,
            updated_at=now,
        )
        if any(existing["id"] == item.id for existing in data["lists"]):
            raise ValueError(f"Todo list already exists: {item.id}")
        data["lists"].append(asdict(item))
        self._save(data)
        return asdict(item)

    def update_list(self, list_id: str, values: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        item = self._find_list(data, list_id)
        item["name"] = _required_text(values, "name") if "name" in values else item["name"]
        item["updated_at"] = _now()
        self._save(data)
        return item

    def delete_list(self, list_id: str) -> bool:
        if list_id == DEFAULT_LIST_ID:
            raise ValueError("The Inbox todo list cannot be deleted.")
        data = self._load()
        original = len(data["lists"])
        data["lists"] = [item for item in data["lists"] if item["id"] != list_id]
        deleted = len(data["lists"]) != original
        if deleted:
            for todo in data["todos"]:
                if todo["list_id"] == list_id:
                    todo["list_id"] = DEFAULT_LIST_ID
                    todo["updated_at"] = _now()
            self._save(data)
        return deleted

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {"lists": [asdict(TodoList(id=DEFAULT_LIST_ID, name="Inbox"))], "todos": []}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        lists = data.get("lists", [])
        todos = data.get("todos", [])
        if not any(item.get("id") == DEFAULT_LIST_ID for item in lists):
            lists.insert(0, asdict(TodoList(id=DEFAULT_LIST_ID, name="Inbox")))
        return {"lists": list(lists), "todos": list(todos)}

    def _save(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _ensure_list(self, data: dict[str, list[dict[str, Any]]], list_id: str) -> None:
        if any(item["id"] == list_id for item in data["lists"]):
            return
        now = _now()
        data["lists"].append(asdict(TodoList(id=list_id, name=list_id.replace("-", " ").title(), created_at=now, updated_at=now)))

    def _find_todo(self, data: dict[str, list[dict[str, Any]]], todo_id: str) -> dict[str, Any]:
        for todo in data["todos"]:
            if todo["id"] == todo_id:
                return todo
        raise FileNotFoundError(f"Todo not found: {todo_id}")

    def _find_list(self, data: dict[str, list[dict[str, Any]]], list_id: str) -> dict[str, Any]:
        for item in data["lists"]:
            if item["id"] == list_id:
                return item
        raise FileNotFoundError(f"Todo list not found: {list_id}")


def proposed_todo(values: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    return {
        "proposed": True,
        "todo": {
            "id": str(values.get("id") or _new_id("todo")),
            "title": _required_text(values, "title"),
            "notes": str(values.get("notes", "")),
            "kind": _literal(values.get("kind", "task"), {"event", "task", "reminder"}, "kind"),
            "list_id": str(values.get("list_id") or DEFAULT_LIST_ID),
            "status": "open",
            "due_at": _optional_iso(values.get("due_at")),
            "remind_at": _optional_iso(values.get("remind_at")),
            "reminder_level": _literal(
                values.get("reminder_level", "normal"),
                {"high", "normal", "none"},
                "reminder_level",
            ),
            "source": _literal(values.get("source", "kairos"), {"manual", "kairos", "chat"}, "source"),
            "source_ref": _optional_str(values.get("source_ref")),
            "reminder_delivery_id": None,
            "reminder_delivered_at": None,
            "created_at": now,
            "updated_at": now,
        },
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _required_text(values: dict[str, Any], key: str) -> str:
    value = str(values.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_str(value: object | None) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _optional_iso(value: object | None) -> str | None:
    if value is None or value == "":
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def _literal(value: object, allowed: set[str], name: str) -> Any:
    text = str(value)
    if text not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return text


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:48]


def _todo_sort_key(todo: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(todo.get("status", "open")),
        str(todo.get("due_at") or todo.get("remind_at") or "9999-12-31T23:59:59+00:00"),
        str(todo.get("created_at", "")),
    )
