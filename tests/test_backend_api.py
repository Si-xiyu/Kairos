from __future__ import annotations

import http.client
import json
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
        assert memories["memories"]
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
