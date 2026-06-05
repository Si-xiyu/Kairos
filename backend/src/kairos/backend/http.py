from __future__ import annotations

from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from kairos.backend.service import KairosBackend


class KairosHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], root: Path) -> None:
        super().__init__(server_address, KairosRequestHandler)
        self.root = Path(root).resolve()
        self.backend = KairosBackend(root)


class KairosRequestHandler(BaseHTTPRequestHandler):
    server: KairosHTTPServer

    def do_OPTIONS(self) -> None:
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            route = parsed.path.rstrip("/") or "/"
            if route == "/api/health":
                self._send_json({"ok": True, "service": "kairos"})
            elif route == "/api/state":
                self._send_json(self.server.backend.state())
            elif route == "/api/today":
                self._send_json(self.server.backend.today())
            elif route == "/api/doctor":
                self._send_json(self.server.backend.doctor())
            elif route == "/api/capabilities":
                self._send_json(self.server.backend.capabilities())
            elif route == "/api/settings":
                self._send_json(self.server.backend.settings())
            elif route == "/api/project-scopes":
                self._send_json(self.server.backend.list_project_scopes())
            elif route == "/api/approvals":
                self._send_json(self.server.backend.list_approvals(status=query.get("status", [None])[0]))
            elif route == "/api/daemon/status":
                self._send_json({"running": False, "transport": "stdlib-http"})
            elif route == "/api/skills":
                self._send_json(self.server.backend.list_skills())
            elif route.startswith("/api/skills/"):
                self._send_json(self.server.backend.read_skill(_route_tail(route, "/api/skills/")))
            elif route == "/api/journals":
                self._send_json(self.server.backend.list_journals(limit=int(query.get("limit", ["30"])[0])))
            elif route == "/api/journal/artifacts":
                self._send_json(
                    self.server.backend.list_journal_artifacts(
                        artifact_type=query.get("type", [None])[0],
                        limit=int(query.get("limit", ["50"])[0]),
                    )
                )
            elif route.startswith("/api/journal/artifacts/"):
                self._send_json(
                    self.server.backend.read_journal_artifact(
                        _route_tail(route, "/api/journal/artifacts/")
                    )
                )
            elif route == "/api/todos":
                self._send_json(
                    self.server.backend.list_todos(
                        status=query.get("status", [None])[0],
                        list_id=query.get("list_id", [None])[0],
                    )
                )
            elif route == "/api/todo-lists":
                self._send_json(self.server.backend.list_todo_lists())
            elif route == "/api/schedules":
                self._send_json(self.server.backend.list_schedules())
            elif route == "/api/sessions":
                self._send_json(self.server.backend.list_sessions(limit=int(query.get("limit", ["50"])[0])))
            elif route.startswith("/api/sessions/"):
                session_id, child = _session_route(route)
                if child == "messages":
                    self._send_json(self.server.backend.list_session_messages(session_id))
                elif child == "events":
                    self._send_json(self.server.backend.list_session_events(session_id))
                elif child == "":
                    self._send_json(self.server.backend.read_session(session_id))
                else:
                    self._send_error(404, f"unknown route: {route}")
            elif route == "/api/memories":
                include = _truthy(query.get("include_candidates", ["false"])[0])
                self._send_json(self.server.backend.list_memories(include_candidates=include))
            elif route == "/api/journal":
                self._send_json(self.server.backend.read_journal(_parse_date(query.get("date", [None])[0])))
            elif route.startswith("/api/"):
                self._send_error(404, f"unknown route: {route}")
            else:
                self._send_static_or_status(route)
        except Exception as exc:
            self._send_error(500, str(exc))

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/") or "/"
            body = self._read_body()
            if route == "/api/bootstrap":
                self._send_json(self.server.backend.bootstrap(force=bool(body.get("force", False))))
            elif route == "/api/sessions":
                self._send_json(
                    self.server.backend.create_session(
                        session_id=str(body["id"]),
                        title=body.get("title"),
                        summary=body.get("summary"),
                    )
                )
            elif route == "/api/reflect":
                self._send_json(
                    self.server.backend.reflect(
                        text=str(body["text"]),
                        journal_date=_parse_date(body.get("date")),
                        source=str(body.get("source", "api")),
                        save_memory_candidates=bool(body.get("save_candidates", True)),
                    )
                )
            elif route == "/api/journal":
                self._send_json(
                    self.server.backend.save_journal(
                        content=str(body["content"]),
                        journal_date=_parse_date(body.get("date")),
                    )
                )
            elif route == "/api/journal/append":
                self._send_json(
                    self.server.backend.append_journal(
                        text=str(body["text"]),
                        journal_date=_parse_date(body.get("date")),
                        heading=str(body.get("heading", "有价值的对话")),
                    )
                )
            elif route == "/api/journal/capture-session":
                self._send_json(
                    self.server.backend.capture_session_to_journal(
                        session_id=str(body["session"]),
                        journal_date=_parse_date(body.get("date")),
                        heading=str(body.get("heading", "有价值的对话")),
                        include_roles=body.get("include_roles"),
                        artifact_type=str(body.get("type", body.get("artifact_type", "diary"))),
                    )
                )
            elif route == "/api/journal/capture":
                self._send_json(self.server.backend.journal_capture(body))
            elif route == "/api/journal/artifacts":
                self._send_json(self.server.backend.create_journal_artifact(body))
            elif route == "/api/journal/artifacts/update":
                self._send_json(self.server.backend.update_journal_artifact(_body_id(body, "artifact_id"), body))
            elif route == "/api/journal/artifacts/delete":
                self._send_json(self.server.backend.delete_journal_artifact(_body_id(body, "artifact_id")))
            elif route == "/api/todos":
                self._send_json(self.server.backend.create_todo(body))
            elif route == "/api/todos/update":
                self._send_json(self.server.backend.update_todo(_body_id(body, "todo_id"), body))
            elif route == "/api/todos/delete":
                self._send_json(self.server.backend.delete_todo(_body_id(body, "todo_id")))
            elif route == "/api/todos/complete":
                self._send_json(self.server.backend.complete_todo(_body_id(body, "todo_id")))
            elif route == "/api/todo-lists":
                self._send_json(self.server.backend.create_todo_list(body))
            elif route == "/api/todo-lists/update":
                self._send_json(self.server.backend.update_todo_list(_body_id(body, "list_id"), body))
            elif route == "/api/todo-lists/delete":
                self._send_json(self.server.backend.delete_todo_list(_body_id(body, "list_id")))
            elif route == "/api/settings":
                self._send_json(self.server.backend.update_settings(body))
            elif route == "/api/project-scopes":
                self._send_json(self.server.backend.create_project_scope(body))
            elif route == "/api/project-scopes/update":
                self._send_json(self.server.backend.update_project_scope(_body_id(body, "scope_id"), body))
            elif route == "/api/project-scopes/delete":
                self._send_json(self.server.backend.delete_project_scope(_body_id(body, "scope_id")))
            elif route == "/api/approvals/approve":
                self._send_json(self.server.backend.approve_action(_body_id(body, "approval_id")))
            elif route == "/api/approvals/reject":
                self._send_json(self.server.backend.reject_action(_body_id(body, "approval_id")))
            elif route == "/api/memories":
                self._send_json(
                    self.server.backend.save_memory(
                        name=str(body["name"]),
                        description=str(body.get("description", "")),
                        content=str(body["content"]),
                        memory_type=str(body.get("type", "user")),
                        scope=str(body.get("scope", "private")),
                        confidence=float(body.get("confidence", 0.7)),
                        source=body.get("source"),
                        candidate=bool(body.get("candidate", False)),
                    )
                )
            elif route == "/api/memories/confirm":
                self._send_json(self.server.backend.confirm_memory(name=str(body["name"])))
            elif route == "/api/memories/update":
                self._send_json(
                    self.server.backend.update_memory(
                        name=str(body["name"]),
                        description=body.get("description"),
                        content=body.get("content"),
                        confidence=float(body["confidence"]) if "confidence" in body else None,
                        candidate=body.get("candidate"),
                    )
                )
            elif route == "/api/memories/delete":
                self._send_json(
                    self.server.backend.delete_memory(
                        name=str(body["name"]),
                        candidate=body.get("candidate"),
                    )
                )
            elif route == "/api/schedules":
                self._send_json(
                    self.server.backend.add_schedule(
                        job_id=str(body["id"]),
                        name=str(body.get("name", body["id"])),
                        kind=str(body.get("kind", "every")),
                        at=_parse_datetime(body.get("at")),
                        seconds=int(body.get("seconds", 3600)),
                        event=str(body.get("event", "daily_journal_check")),
                        message=body.get("message"),
                        due_now=bool(body.get("due_now", False)),
                    )
                )
            elif route == "/api/schedules/delete":
                self._send_json(self.server.backend.delete_schedule(job_id=str(body["id"])))
            elif route == "/api/schedules/toggle":
                self._send_json(
                    self.server.backend.set_schedule_enabled(
                        job_id=str(body["id"]),
                        enabled=bool(body["enabled"]),
                    )
                )
            elif route == "/api/daemon/tick":
                self._send_json(self.server.backend.daemon_tick())
            elif route == "/api/daemon/status":
                self._send_json({"running": False, "transport": "stdlib-http"})
            elif route == "/api/heartbeat/tick":
                self._send_json(
                    self.server.backend.heartbeat_tick(
                        force=bool(body.get("force", False)),
                        user_active=bool(body.get("user_active", False)),
                        do_not_disturb=bool(body.get("do_not_disturb", False)),
                        channel=str(body.get("channel", "windows_toast")),
                        to=str(body.get("to", "local-user")),
                    )
                )
            elif route == "/api/chat":
                self._send_json(
                    self.server.backend.chat_once(
                        text=str(body["text"]),
                        session=str(body.get("session", "default")),
                        autonomy=int(body.get("autonomy", 3)),
                    )
                )
            elif route == "/api/reviews/weekly":
                self._send_json(
                    self.server.backend.weekly_review(
                        start_date=_parse_date(body.get("start_date")),
                        end_date=_parse_date(body.get("end_date")),
                    )
                )
            else:
                self._send_error(404, f"unknown route: {route}")
        except KeyError as exc:
            self._send_error(400, f"missing required field: {exc}")
        except Exception as exc:
            self._send_error(500, str(exc))

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("request body must be a JSON object")
        return data

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"ok": False, "error": message}, status=status)

    def _send_static_or_status(self, route: str) -> None:
        static_root = _static_root(self.server.root)
        if static_root is None:
            if route != "/":
                self._send_error(404, f"unknown route: {route}")
                return
            self._send_json(
                {
                    "ok": True,
                    "service": "kairos",
                    "message": "Kairos backend is running.",
                    "api": "/api/state",
                }
            )
            return

        path = (static_root / route.lstrip("/")).resolve()
        if path == static_root or path.is_dir():
            path = path / "index.html"
        if not path.is_relative_to(static_root) or not path.exists() or not path.is_file():
            path = static_root / "index.html"
        if not path.exists():
            self._send_error(404, f"unknown route: {route}")
            return

        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


def run_server(host: str, port: int, root: Path) -> None:
    server = KairosHTTPServer((host, port), root=root)
    print(f"Kairos backend listening on http://{host}:{port}")
    print(f"Kairos root: {Path(root).resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nKairos backend stopped.")
    finally:
        server.server_close()


def _parse_date(raw: object | None) -> date | None:
    if raw is None or raw == "":
        return None
    return date.fromisoformat(str(raw))


def _parse_datetime(raw: object | None) -> datetime | None:
    if raw is None or raw == "":
        return None
    parsed = datetime.fromisoformat(str(raw))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _truthy(raw: str) -> bool:
    return raw.lower() in {"1", "true", "yes", "on"}


def _body_id(body: dict[str, Any], alias: str) -> str:
    value = body.get("id", body.get(alias, ""))
    if not value:
        raise ValueError("id is required")
    return str(value)


def _route_tail(route: str, prefix: str) -> str:
    from urllib.parse import unquote

    return unquote(route[len(prefix) :])


def _session_route(route: str) -> tuple[str, str]:
    from urllib.parse import unquote

    tail = route[len("/api/sessions/") :]
    parts = tail.split("/", 1)
    session_id = unquote(parts[0])
    child = parts[1] if len(parts) > 1 else ""
    return session_id, child


def _static_root(root: Path) -> Path | None:
    for candidate in (
        root / "frontend" / "dist",
        root / "frontend" / "build",
        root / "web" / "dist",
        root / "web" / "build",
        root / "public",
    ):
        if (candidate / "index.html").exists():
            return candidate
    return None
