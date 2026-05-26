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


def test_backend_service_schedule_tick_and_chat(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)
    backend.bootstrap()
    backend.add_schedule(
        job_id="demo",
        name="Demo",
        message="要写日记吗？",
        due_now=True,
    )

    tick = backend.daemon_tick()
    chat = backend.chat_once("/tool file.list path=.", session="api-test")

    assert tick["due_jobs"] == 1
    assert tick["delivery"]["delivered"] == 1
    assert tick["delivered"][0]["text"] == "要写日记吗？"
    assert chat["outbound"]
    assert "tool file.list: ok" in chat["outbound"][0]["text"]


def test_backend_service_application_state_and_crud(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)
    backend.bootstrap()

    journal = backend.save_journal("# 2026-05-16\n\n## 今天发生了什么\n\n写 Kairos 后端。")
    backend.append_journal("补齐第一轮 API。", heading="做了哪些事情")
    memory = backend.save_memory(
        name="prefers_architecture_first",
        description="User likes discussing architecture first.",
        content="用户喜欢先讨论架构，再进入实现。",
        candidate=True,
    )
    confirmed = backend.confirm_memory(memory["memory"]["name"])
    backend.add_schedule(job_id="check", name="Check", due_now=True)
    backend.set_schedule_enabled("check", False)

    state = backend.state()
    journals = backend.list_journals()
    memories = backend.list_memories(include_candidates=True)
    schedules = backend.list_schedules()
    deleted = backend.delete_schedule("check")

    assert journal["exists"] is True
    assert journals["journals"]
    assert confirmed["memory"]["candidate"] is False
    assert memories["summary"]["confirmed"] == 1
    assert all("candidate_reason" in memory for memory in memories["memories"])
    assert next(job for job in schedules["schedules"] if job["id"] == "check")["enabled"] is False
    assert state["capabilities"]["tools"] >= 3
    assert deleted["deleted"] is True


def test_backend_service_frontend_session_adapter(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)
    backend.create_session(
        session_id="session-ui",
        title="UI integration",
        summary="Frontend adapter smoke session.",
    )
    backend.chat_once("/tool file.list path=.", session="session-ui")

    sessions = backend.list_sessions()
    session = backend.read_session("session-ui")
    messages = backend.list_session_messages("session-ui")
    events = backend.list_session_events("session-ui")
    chat = backend.chat_once("plain follow up", session="session-ui")
    state = backend.state()

    assert sessions["sessions"][0]["id"] == "session-ui"
    assert session["session"]["id"] == "session-ui"
    assert messages["messages"][0]["sessionId"] == "session-ui"
    assert any(message["author"] == "Kairos" for message in messages["messages"])
    assert any(event["kind"] == "tool_result" for event in events["events"])
    assert chat["session"]["id"] == "session-ui"
    assert chat["messages"]
    assert chat["events"]
    assert state["sessions"]


def test_backend_service_captures_session_to_journal(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)
    backend.chat_once("今天和 Kairos 讨论了日记捕获。", session="daily-chat")
    captured = backend.capture_session_to_journal("daily-chat")

    assert captured["captured"] >= 2
    assert "来源会话：`daily-chat`" in captured["content"]
    assert "今天和 Kairos 讨论了日记捕获" in captured["content"]


def test_backend_service_weekly_review_summarizes_journals(tmp_path: Path) -> None:
    backend = KairosBackend(tmp_path)
    backend.save_journal(
        "# 2026-05-16\n\n## 做了哪些事情\n\n实现 FastAPI 后端，很有成就。\n\n## 情绪与能量\n\n前端同步反复消耗，但架构讨论有能量。",
        journal_date=date(2026, 5, 16),
    )

    review = backend.weekly_review(
        start_date=date(2026, 5, 16),
        end_date=date(2026, 5, 16),
    )

    assert review["sections"]["这一周你做了什么"]
    assert review["sections"]["哪些事情给你能量"]
    assert review["sections"]["哪些事情反复消耗你"]
    assert "实现 FastAPI 后端" in review["content"]
    assert "优先减少反复消耗项" in review["content"]


def test_backend_service_capabilities_discovers_skills(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "journal-coach"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: journal-coach\ndescription: Guide reflective journaling.\n---\n\n# Journal Coach\n",
        encoding="utf-8",
    )
    backend = KairosBackend(tmp_path)

    skills = backend.list_skills()
    skill = backend.read_skill("journal-coach")
    capabilities = backend.capabilities()

    assert skills["skills"][0]["name"] == "journal-coach"
    assert "Journal Coach" in skill["body"]
    assert capabilities["skills"][0]["name"] == "journal-coach"


def test_http_api_health_and_reflect(tmp_path: Path) -> None:
    server = KairosHTTPServer(("127.0.0.1", 0), root=tmp_path)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        health = _request(host, port, "GET", "/api/health")
        bootstrap = _request(host, port, "POST", "/api/bootstrap", {})
        reflected = _request(
            host,
            port,
            "POST",
            "/api/reflect",
            {"text": "我喜欢先讨论架构，今天很有能量", "date": "2026-05-16"},
        )
        memories = _request(host, port, "GET", "/api/memories?include_candidates=true")

        assert health["ok"] is True
        assert bootstrap["default_nightly_journal"] == "installed"
        assert reflected["candidate_count"] >= 1
        assert reflected["candidates"][0]["reason"]
        assert memories["memories"]
        assert memories["memories"][0]["source_journal_date"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_api_application_endpoints(tmp_path: Path) -> None:
    server = KairosHTTPServer(("127.0.0.1", 0), root=tmp_path)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _request(host, port, "POST", "/api/bootstrap", {})
        saved = _request(
            host,
            port,
            "POST",
            "/api/journal",
            {"date": "2026-05-16", "content": "# 2026-05-16\n\nhello"},
        )
        _request(host, port, "POST", "/api/chat", {"text": "写进日记", "session": "http-daily"})
        captured = _request(
            host,
            port,
            "POST",
            "/api/journal/capture-session",
            {"date": "2026-05-16", "session": "http-daily"},
        )
        journals = _request(host, port, "GET", "/api/journals")
        state = _request(host, port, "GET", "/api/state")
        session = _request(
            host,
            port,
            "POST",
            "/api/sessions",
            {"id": "http-ui", "title": "HTTP UI"},
        )
        schedule = _request(
            host,
            port,
            "POST",
            "/api/schedules",
            {"id": "front", "name": "Frontend", "due_now": True},
        )
        schedules = _request(host, port, "GET", "/api/schedules")
        sessions = _request(host, port, "GET", "/api/sessions")
        session_detail = _request(host, port, "GET", "/api/sessions/http-ui")
        messages = _request(host, port, "GET", "/api/sessions/http-ui/messages")
        events = _request(host, port, "GET", "/api/sessions/http-ui/events")
        toggled = _request(
            host,
            port,
            "POST",
            "/api/schedules/toggle",
            {"id": schedule["id"], "enabled": False},
        )
        review = _request(
            host,
            port,
            "POST",
            "/api/reviews/weekly",
            {"start_date": "2026-05-16", "end_date": "2026-05-16"},
        )

        assert saved["content"].startswith("# 2026-05-16")
        assert captured["captured"] >= 1
        assert journals["journals"][0]["date"] == "2026-05-16"
        assert state["app"]["name"] == "Kairos"
        assert session["session"]["id"] == "http-ui"
        assert sessions["sessions"]
        assert session_detail["session"]["id"] == "http-ui"
        assert messages["messages"]
        assert events["events"]
        assert schedules["schedules"]
        assert toggled["updated"] is True
        assert "2026-05-16" in review["content"]
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
