from __future__ import annotations

import http.client
import json
from datetime import date
from pathlib import Path
from threading import Thread

from kairos.backend.http import KairosHTTPServer
from kairos.backend.service import KairosBackend


def test_backend_service_reflect_and_doctor(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)

    bootstrap = backend.bootstrap()
    reflected = backend.reflect("我喜欢先讨论架构，今天很有能量", save_memory_candidates=True)
    doctor = backend.doctor()

    assert bootstrap["default_nightly_journal"] == "installed"
    assert reflected["candidate_count"] >= 1
    assert reflected["candidates"][0]["reason"]
    assert doctor["journals"] == 1
    assert doctor["memory_candidates"] >= 1
    assert doctor["schedules"] == 1


def test_backend_service_today_todo_and_journal_artifacts(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)
    backend.bootstrap()

    todo_list = backend.create_todo_list({"name": "Work"})["list"]
    todo = backend.create_todo(
        {
            "title": "提交后端 API",
            "notes": "覆盖 Today 和 Todo MVP",
            "kind": "task",
            "list_id": todo_list["id"],
            "due_at": "2026-05-16T12:00:00+00:00",
            "reminder_level": "high",
            "source": "manual",
        }
    )["todo"]
    artifact = backend.create_journal_artifact(
        {
            "type": "record",
            "title": "Backend slice",
            "summary": "Today, Todo, Journal artifact",
            "tags": ["kairos"],
            "source": {"kind": "manual", "session_id": None},
            "body": "实现后端可用切片。",
        }
    )["artifact"]

    today = backend.today()
    completed = backend.complete_todo(todo["id"])["todo"]
    artifacts = backend.list_journal_artifacts()["artifacts"]

    assert today["todos"]["items"][0]["title"] == "提交后端 API"
    assert today["memory"]["pending_candidates"] == 0
    assert today["model"]["suggested_provider"] == "deepseek"
    assert completed["status"] == "completed"
    assert artifacts[0]["id"] == artifact["id"]


def test_backend_service_schedule_tick_chat_and_weekly_review(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)
    backend.bootstrap()
    backend.add_schedule(job_id="demo", name="Demo", message="要写日记吗？", due_now=True)
    backend.save_journal(
        "# 2026-05-16\n\n## 做了哪些事情\n\n实现 FastAPI 后端，很有成就。\n\n## 情绪与能量\n\n前端同步反复消耗，但架构讨论有能量。",
        journal_date=date(2026, 5, 16),
    )

    tick = backend.daemon_tick()
    chat = backend.chat_once("/tool file.list path=.", session="api-test")
    review = backend.weekly_review(start_date=date(2026, 5, 16), end_date=date(2026, 5, 16))

    assert tick["due_jobs"] == 1
    assert tick["delivery"]["delivered"] == 1
    assert tick["delivered"][0]["text"] == "要写日记吗？"
    assert "tool file.list: ok" in chat["outbound"][0]["text"]
    assert review["sections"]["这一周你做了什么"]
    assert review["sections"]["哪些事情给你能量"]
    assert review["sections"]["哪些事情反复消耗你"]


def test_backend_service_frontend_session_adapter_and_capture(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)
    backend.create_session(
        session_id="session-ui",
        title="UI integration",
        summary="Frontend adapter smoke session.",
    )
    backend.chat_once("/tool file.list path=.", session="session-ui")
    backend.chat_once("今天和 Kairos 讨论了日记捕获。", session="daily-chat")

    sessions = backend.list_sessions()
    messages = backend.list_session_messages("session-ui")
    events = backend.list_session_events("session-ui")
    captured = backend.capture_session_to_journal("daily-chat")
    state = backend.state()

    assert sessions["sessions"][0]["id"] in {"daily-chat", "session-ui"}
    assert messages["messages"][0]["sessionId"] == "session-ui"
    assert any(event["kind"] == "tool_result" for event in events["events"])
    assert captured["captured"] >= 2
    assert "来源会话：`daily-chat`" in captured["content"]
    assert state["sessions"]


def test_http_api_application_endpoints(tmp_path: Path) -> None:
    server = KairosHTTPServer(("127.0.0.1", 0), root=tmp_path)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        health = _request(host, port, "GET", "/api/health")
        _request(host, port, "POST", "/api/bootstrap", {})
        reflected = _request(
            host,
            port,
            "POST",
            "/api/reflect",
            {"text": "我喜欢先讨论架构，今天很有能量", "date": "2026-05-16"},
        )
        todo_list = _request(host, port, "POST", "/api/todo-lists", {"name": "HTTP Work"})["list"]
        todo = _request(
            host,
            port,
            "POST",
            "/api/todos",
            {"title": "HTTP todo", "list_id": todo_list["id"], "due_at": "2026-05-16T12:00:00+00:00"},
        )["todo"]
        artifact = _request(
            host,
            port,
            "POST",
            "/api/journal/artifacts",
            {"type": "diary", "title": "Daily note", "date": "2026-05-16", "body": "今天推进了后端。"},
        )["artifact"]
        today = _request(host, port, "GET", "/api/today")
        completed = _request(host, port, "POST", "/api/todos/complete", {"id": todo["id"]})
        read_artifact = _request(host, port, "GET", f"/api/journal/artifacts/{artifact['id']}")

        assert health["ok"] is True
        assert reflected["candidate_count"] >= 1
        assert today["todos"]["items"][0]["id"] == todo["id"]
        assert completed["todo"]["status"] == "completed"
        assert read_artifact["artifact"]["title"] == "Daily note"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_static_status_and_frontend_hosting(tmp_path: Path) -> None:
    server = KairosHTTPServer(("127.0.0.1", 0), root=tmp_path)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, headers, body = _raw_request(host, port, "GET", "/")
        assert status == 200
        assert headers["content-type"].startswith("application/json")
        assert "Kairos backend is running" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    public = tmp_path / "public"
    public.mkdir()
    (public / "index.html").write_text("<!doctype html><title>Kairos UI</title>", encoding="utf-8")
    (public / "app.js").write_text("console.log('kairos')", encoding="utf-8")

    server = KairosHTTPServer(("127.0.0.1", 0), root=tmp_path)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, headers, body = _raw_request(host, port, "GET", "/")
        assert status == 200
        assert "text/html" in headers["content-type"]
        assert "Kairos UI" in body

        status, headers, body = _raw_request(host, port, "GET", "/app.js")
        assert status == 200
        assert "javascript" in headers["content-type"]
        assert "kairos" in body

        status, headers, body = _raw_request(host, port, "GET", "/deep/link")
        assert status == 200
        assert "Kairos UI" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(
    host: str,
    port: int,
    method: str,
    path: str,
    body: dict | None = None,
) -> dict:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=payload, headers=headers)
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    conn.close()
    assert response.status < 400, data
    return json.loads(data)


def _raw_request(host: str, port: int, method: str, path: str) -> tuple[int, dict[str, str], str]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request(method, path)
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    headers = {key.lower(): value for key, value in response.getheaders()}
    conn.close()
    return response.status, headers, data
