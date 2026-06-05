from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from kairos.backend.fastapi_app import create_app


def test_fastapi_health_state_today_and_chat(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    health = client.get("/api/health")
    bootstrap = client.post("/api/bootstrap", json={})
    chat = client.post("/api/chat", json={"text": "/tool file.list path=.", "session": "fastapi"})
    today = client.get("/api/today")
    state = client.get("/api/state")

    assert health.status_code == 200
    assert health.json()["service"] == "kairos"
    assert bootstrap.json()["default_nightly_journal"] == "installed"
    assert "tool file.list: ok" in chat.json()["outbound"][0]["text"]
    assert today.json()["model"]["suggested_provider"] == "deepseek"
    assert today.json()["todos"]["available"] is True
    assert state.json()["app"]["name"] == "Kairos"


def test_fastapi_todo_and_journal_artifact_workflow(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/bootstrap", json={})

    todo_list = client.post("/api/todo-lists", json={"name": "FastAPI"}).json()["list"]
    todo = client.post(
        "/api/todos",
        json={
            "title": "补齐 FastAPI Todo",
            "list_id": todo_list["id"],
            "kind": "task",
            "due_at": "2026-05-16T12:00:00+00:00",
        },
    )
    artifact = client.post(
        "/api/journal/artifacts",
        json={
            "type": "record",
            "title": "FastAPI artifact",
            "summary": "Journal artifact route",
            "body": "记录 API 行为。",
        },
    )
    todos = client.get("/api/todos")
    artifacts = client.get("/api/journal/artifacts")
    completed = client.post("/api/todos/complete", json={"id": todo.json()["todo"]["id"]})

    assert todo.status_code == 200
    assert artifact.status_code == 200
    assert todos.json()["todos"][0]["title"] == "补齐 FastAPI Todo"
    assert artifacts.json()["artifacts"][0]["title"] == "FastAPI artifact"
    assert completed.json()["todo"]["status"] == "completed"


def test_fastapi_settings_project_scopes_approvals_and_capture(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/bootstrap", json={})

    settings = client.post(
        "/api/settings",
        json={
            "llm": {
                "provider": "openai-compatible",
                "api_key": "secret-key",
                "model": "deepseek-chat",
            }
        },
    )
    scope = client.post(
        "/api/project-scopes",
        json={"name": "Root", "path": ".", "permissions": {"read": True, "write": True}},
    )
    proposed = client.post(
        "/api/chat",
        json={
            "text": '/tool todo.propose title="Review proposal" remind_at=2026-01-01T09:00:00+00:00 reminder_level=high source=chat',
            "autonomy": 3,
        },
    )
    approvals = client.get("/api/approvals", params={"status": "pending"})
    approved = client.post("/api/approvals/approve", json={"id": approvals.json()["actions"][0]["id"]})
    capture = client.post(
        "/api/journal/capture",
        json={"type": "record", "title": "API capture", "text": "Discussed API capture.\nTodo: inspect Journal."},
    )
    today = client.get("/api/today")

    assert settings.status_code == 200
    assert settings.json()["llm"]["api_key_configured"] is True
    assert "secret-key" not in settings.text
    assert scope.json()["scope"]["permission_summary"] == "read, write"
    assert "waiting for confirmation" in proposed.json()["outbound"][0]["text"]
    assert approved.json()["result"]["todo"]["title"] == "Review proposal"
    assert capture.json()["message"] == "已加入记录"
    assert today.json()["approvals"]["available"] is True


def test_fastapi_journal_memory_schedule_workflow(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/bootstrap", json={})

    journal = client.post(
        "/api/journal",
        json={"date": "2026-05-16", "content": "# 2026-05-16\n\nhello"},
    )
    reflected = client.post(
        "/api/reflect",
        json={"date": "2026-05-16", "text": "我喜欢先讨论架构，今天很有能量"},
    )
    memories = client.get("/api/memories", params={"include_candidates": "true"})
    schedule = client.post(
        "/api/schedules",
        json={"id": "fastapi-reminder", "name": "Reminder", "due_now": True},
    )
    toggled = client.post(
        "/api/schedules/toggle",
        json={"id": "fastapi-reminder", "enabled": False},
    )
    schedules = client.get("/api/schedules")

    assert journal.status_code == 200
    assert reflected.json()["candidate_count"] >= 1
    assert memories.json()["summary"]["candidates"] >= 1
    assert memories.json()["memories"][0]["source_journal_date"] == "2026-05-16"
    assert schedule.json()["id"] == "fastapi-reminder"
    assert toggled.json()["updated"] is True
    assert any(job["id"] == "fastapi-reminder" for job in schedules.json()["schedules"])


def test_fastapi_heartbeat_tick_exposes_presence_session(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    heartbeat = client.post("/api/heartbeat/tick", json={"force": True, "channel": "cli"})
    events = client.get("/api/sessions/kairos-presence/events")

    assert heartbeat.status_code == 200
    assert heartbeat.json()["heartbeat"]["message"]
    assert heartbeat.json()["session"]["id"] == "kairos-presence"
    assert events.json()["events"]


def test_fastapi_daemon_start_status_stop(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    started = client.post("/api/daemon/start")
    status = client.get("/api/daemon/status")
    stopped = client.post("/api/daemon/stop")

    assert started.status_code == 200
    assert started.json()["running"] is True
    assert status.json()["running"] in {True, False}
    assert "tick_count" in status.json()
    assert stopped.json()["running"] is False


def test_fastapi_static_hosting(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    (public / "index.html").write_text("<!doctype html><title>Kairos</title>", encoding="utf-8")
    (public / "app.js").write_text("console.log('kairos')", encoding="utf-8")

    client = TestClient(create_app(tmp_path))
    root = client.get("/")
    js = client.get("/app.js")
    deep = client.get("/deep/link")

    assert root.status_code == 200
    assert "Kairos" in root.text
    assert js.status_code == 200
    assert "kairos" in js.text
    assert deep.status_code == 200
    assert "Kairos" in deep.text
