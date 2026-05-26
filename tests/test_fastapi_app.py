from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from kairos.backend.fastapi_app import create_app


def test_fastapi_health_state_and_chat(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    health = client.get("/api/health")
    bootstrap = client.post("/api/bootstrap", json={})
    chat = client.post("/api/chat", json={"text": "/tool file.list path=.", "session": "fastapi"})
    sessions = client.get("/api/sessions")
    session = client.get("/api/sessions/fastapi")
    messages = client.get("/api/sessions/fastapi/messages")
    events = client.get("/api/sessions/fastapi/events")
    state = client.get("/api/state")

    assert health.status_code == 200
    assert health.json()["service"] == "kairos"
    assert bootstrap.json()["default_nightly_journal"] == "installed"
    assert "tool file.list: ok" in chat.json()["outbound"][0]["text"]
    assert chat.json()["session"]["id"] == "fastapi"
    assert chat.json()["messages"]
    assert any(event["kind"] == "tool_result" for event in chat.json()["events"])
    assert sessions.json()["sessions"]
    assert session.json()["session"]["id"] == "fastapi"
    assert messages.json()["messages"]
    assert events.json()["events"]
    assert state.json()["app"]["name"] == "Kairos"


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
    assert reflected.json()["candidates"][0]["reason"]
    assert memories.json()["summary"]["candidates"] >= 1
    assert memories.json()["memories"][0]["candidate_reason"]
    assert memories.json()["memories"][0]["source_journal_date"] == "2026-05-16"
    assert schedule.json()["id"] == "fastapi-reminder"
    assert toggled.json()["updated"] is True
    assert any(job["id"] == "fastapi-reminder" for job in schedules.json()["schedules"])


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
