from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from kairos.backend.service import KairosBackend
from kairos.presence import BackgroundDaemon


def create_app(root: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if str(os.environ.get("KAIROS_DAEMON_AUTOSTART", "")).lower() in {"1", "true", "yes", "on"}:
            _daemon(app).start()
        try:
            yield
        finally:
            _daemon(app).stop()

    app = FastAPI(title="Kairos Backend", version="0.1.0", lifespan=lifespan)
    app.state.root = Path(root).resolve()
    app.state.backend = KairosBackend(app.state.root)
    app.state.daemon = BackgroundDaemon(
        tick_fn=lambda: _backend(app).daemon_tick(),
        interval_seconds=float(os.environ.get("KAIROS_DAEMON_INTERVAL_SECONDS", "60")),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "kairos"}

    @app.post("/api/bootstrap")
    def bootstrap(body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        return _backend(app).bootstrap(force=bool(body.get("force", False)))

    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return _backend(app).state()

    @app.get("/api/today")
    def today() -> dict[str, Any]:
        return _backend(app).today()

    @app.get("/api/doctor")
    def doctor() -> dict[str, Any]:
        return _backend(app).doctor()

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, Any]:
        return _backend(app).capabilities()

    @app.get("/api/settings")
    def settings() -> dict[str, Any]:
        return _backend(app).settings()

    @app.post("/api/settings")
    def update_settings(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).update_settings(body)

    @app.get("/api/project-scopes")
    def project_scopes() -> dict[str, Any]:
        return _backend(app).list_project_scopes()

    @app.post("/api/project-scopes")
    def create_project_scope(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).create_project_scope(body)

    @app.post("/api/project-scopes/update")
    def update_project_scope(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).update_project_scope(_body_id(body, "scope_id"), body)

    @app.post("/api/project-scopes/delete")
    def delete_project_scope(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).delete_project_scope(_body_id(body, "scope_id"))

    @app.get("/api/approvals")
    def approvals(status: str | None = None) -> dict[str, Any]:
        return _backend(app).list_approvals(status=status)

    @app.post("/api/approvals/approve")
    def approve_action(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).approve_action(_body_id(body, "approval_id"))

    @app.post("/api/approvals/reject")
    def reject_action(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).reject_action(_body_id(body, "approval_id"))

    @app.get("/api/skills")
    def skills() -> dict[str, Any]:
        return _backend(app).list_skills()

    @app.get("/api/skills/{name}")
    def skill(name: str) -> dict[str, Any]:
        return _backend(app).read_skill(name)

    @app.get("/api/sessions")
    def sessions(limit: int = 50) -> dict[str, Any]:
        return _backend(app).list_sessions(limit=limit)

    @app.post("/api/sessions")
    def create_session(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).create_session(
            session_id=str(body["id"]),
            title=body.get("title"),
            summary=body.get("summary"),
        )

    @app.get("/api/sessions/{session_id}/messages")
    def session_messages(session_id: str) -> dict[str, Any]:
        return _backend(app).list_session_messages(session_id)

    @app.get("/api/sessions/{session_id}/events")
    def session_events(session_id: str) -> dict[str, Any]:
        return _backend(app).list_session_events(session_id)

    @app.get("/api/sessions/{session_id}")
    def session(session_id: str) -> dict[str, Any]:
        return _backend(app).read_session(session_id)

    @app.post("/api/reflect")
    def reflect(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).reflect(
            text=str(body["text"]),
            journal_date=_parse_date(body.get("date")),
            source=str(body.get("source", "api")),
            save_memory_candidates=bool(body.get("save_candidates", True)),
        )

    @app.get("/api/journals")
    def journals(limit: int = 30) -> dict[str, Any]:
        return _backend(app).list_journals(limit=limit)

    @app.get("/api/journal/artifacts")
    def journal_artifacts(type: str | None = None, limit: int = 50) -> dict[str, Any]:
        return _backend(app).list_journal_artifacts(artifact_type=type, limit=limit)

    @app.get("/api/journal/artifacts/{artifact_id}")
    def journal_artifact(artifact_id: str) -> dict[str, Any]:
        return _backend(app).read_journal_artifact(artifact_id)

    @app.post("/api/journal/artifacts")
    def create_journal_artifact(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).create_journal_artifact(body)

    @app.post("/api/journal/artifacts/update")
    def update_journal_artifact(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).update_journal_artifact(_body_id(body, "artifact_id"), body)

    @app.post("/api/journal/artifacts/delete")
    def delete_journal_artifact(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).delete_journal_artifact(_body_id(body, "artifact_id"))

    @app.get("/api/journal")
    def journal(date: str | None = None) -> dict[str, Any]:
        return _backend(app).read_journal(_parse_date(date))

    @app.post("/api/journal")
    def save_journal(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).save_journal(
            content=str(body["content"]),
            journal_date=_parse_date(body.get("date")),
        )

    @app.post("/api/journal/append")
    def append_journal(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).append_journal(
            text=str(body["text"]),
            journal_date=_parse_date(body.get("date")),
            heading=str(body.get("heading", "有价值的对话")),
        )

    @app.post("/api/journal/capture-session")
    def capture_session(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).capture_session_to_journal(
            session_id=str(body["session"]),
            journal_date=_parse_date(body.get("date")),
            heading=str(body.get("heading", "有价值的对话")),
            include_roles=body.get("include_roles"),
            artifact_type=str(body.get("type", body.get("artifact_type", "diary"))),
        )

    @app.post("/api/journal/capture")
    def journal_capture(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).journal_capture(body)

    @app.get("/api/todos")
    def todos(status: str | None = None, list_id: str | None = None) -> dict[str, Any]:
        return _backend(app).list_todos(status=status, list_id=list_id)

    @app.post("/api/todos")
    def create_todo(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).create_todo(body)

    @app.post("/api/todos/update")
    def update_todo(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).update_todo(_body_id(body, "todo_id"), body)

    @app.post("/api/todos/delete")
    def delete_todo(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).delete_todo(_body_id(body, "todo_id"))

    @app.post("/api/todos/complete")
    def complete_todo(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).complete_todo(_body_id(body, "todo_id"))

    @app.get("/api/todo-lists")
    def todo_lists() -> dict[str, Any]:
        return _backend(app).list_todo_lists()

    @app.post("/api/todo-lists")
    def create_todo_list(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).create_todo_list(body)

    @app.post("/api/todo-lists/update")
    def update_todo_list(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).update_todo_list(_body_id(body, "list_id"), body)

    @app.post("/api/todo-lists/delete")
    def delete_todo_list(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).delete_todo_list(_body_id(body, "list_id"))

    @app.get("/api/memories")
    def memories(include_candidates: bool = False) -> dict[str, Any]:
        return _backend(app).list_memories(include_candidates=include_candidates)

    @app.post("/api/memories")
    def save_memory(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).save_memory(
            name=str(body["name"]),
            description=str(body.get("description", "")),
            content=str(body["content"]),
            memory_type=str(body.get("type", "user")),
            scope=str(body.get("scope", "private")),
            confidence=float(body.get("confidence", 0.7)),
            source=body.get("source"),
            candidate=bool(body.get("candidate", False)),
        )

    @app.post("/api/memories/confirm")
    def confirm_memory(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).confirm_memory(name=str(body["name"]))

    @app.post("/api/memories/update")
    def update_memory(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).update_memory(
            name=str(body["name"]),
            description=body.get("description"),
            content=body.get("content"),
            confidence=float(body["confidence"]) if "confidence" in body else None,
            candidate=body.get("candidate"),
        )

    @app.post("/api/memories/delete")
    def delete_memory(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).delete_memory(
            name=str(body["name"]),
            candidate=body.get("candidate"),
        )

    @app.get("/api/schedules")
    def schedules() -> dict[str, Any]:
        return _backend(app).list_schedules()

    @app.post("/api/schedules")
    def add_schedule(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).add_schedule(
            job_id=str(body["id"]),
            name=str(body.get("name", body["id"])),
            kind=str(body.get("kind", "every")),
            at=_parse_datetime(body.get("at")),
            seconds=int(body.get("seconds", 3600)),
            event=str(body.get("event", "daily_journal_check")),
            message=body.get("message"),
            due_now=bool(body.get("due_now", False)),
        )

    @app.post("/api/schedules/delete")
    def delete_schedule(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).delete_schedule(job_id=str(body["id"]))

    @app.post("/api/schedules/toggle")
    def toggle_schedule(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).set_schedule_enabled(
            job_id=str(body["id"]),
            enabled=bool(body["enabled"]),
        )

    @app.post("/api/daemon/tick")
    def daemon_tick() -> dict[str, Any]:
        return _backend(app).daemon_tick()

    @app.get("/api/daemon/status")
    def daemon_status() -> dict[str, Any]:
        return _daemon(app).get_status()

    @app.post("/api/daemon/start")
    def daemon_start() -> dict[str, Any]:
        return _daemon(app).start()

    @app.post("/api/daemon/stop")
    def daemon_stop() -> dict[str, Any]:
        return _daemon(app).stop()

    @app.post("/api/heartbeat/tick")
    def heartbeat_tick(body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        return _backend(app).heartbeat_tick(
            force=bool(body.get("force", False)),
            user_active=bool(body.get("user_active", False)),
            do_not_disturb=bool(body.get("do_not_disturb", False)),
            channel=str(body.get("channel", "windows_toast")),
            to=str(body.get("to", "local-user")),
        )

    @app.post("/api/chat")
    def chat(body: dict[str, Any]) -> dict[str, Any]:
        return _backend(app).chat_once(
            text=str(body["text"]),
            session=str(body.get("session", "default")),
            autonomy=int(body.get("autonomy", 3)),
        )

    @app.post("/api/reviews/weekly")
    def weekly_review(body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        return _backend(app).weekly_review(
            start_date=_parse_date(body.get("start_date")),
            end_date=_parse_date(body.get("end_date")),
        )

    @app.get("/{path:path}")
    def static_or_status(path: str, request: Request) -> Any:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"unknown route: /{path}")
        static_root = _static_root(app.state.root)
        if static_root is None:
            if path:
                raise HTTPException(status_code=404, detail=f"unknown route: /{path}")
            return JSONResponse(
                {
                    "ok": True,
                    "service": "kairos",
                    "message": "Kairos backend is running.",
                    "api": "/api/state",
                }
            )
        target = (static_root / path).resolve()
        if target == static_root or target.is_dir():
            target = target / "index.html"
        if not target.is_relative_to(static_root) or not target.exists() or not target.is_file():
            target = static_root / "index.html"
        return FileResponse(target)

    return app


def run_server(host: str, port: int, root: Path) -> None:
    print(f"Kairos FastAPI backend listening on http://{host}:{port}")
    print(f"Kairos root: {Path(root).resolve()}")
    uvicorn.run(create_app(root), host=host, port=port)


def _backend(app: FastAPI) -> KairosBackend:
    return app.state.backend


def _daemon(app: FastAPI) -> BackgroundDaemon:
    return app.state.daemon


def _parse_date(raw: object | None) -> date | None:
    if raw is None or raw == "":
        return None
    return date.fromisoformat(str(raw))


def _parse_datetime(raw: object | None):
    if raw is None or raw == "":
        return None
    from datetime import datetime, timezone

    parsed = datetime.fromisoformat(str(raw))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _body_id(body: dict[str, Any], alias: str) -> str:
    value = body.get("id", body.get(alias, ""))
    if not value:
        raise ValueError("id is required")
    return str(value)


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
