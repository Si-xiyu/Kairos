from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from kairos.backend.service import KairosBackend


def create_app(root: Path) -> FastAPI:
    app = FastAPI(title="Kairos Backend", version="0.1.0")
    app.state.root = Path(root).resolve()
    app.state.backend = KairosBackend(app.state.root)
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

    @app.get("/api/doctor")
    def doctor() -> dict[str, Any]:
        return _backend(app).doctor()

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, Any]:
        return _backend(app).capabilities()

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
        )

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
