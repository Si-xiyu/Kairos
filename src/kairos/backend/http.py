from __future__ import annotations

from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from kairos.backend.service import KairosBackend


class KairosHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], root: Path) -> None:
        super().__init__(server_address, KairosRequestHandler)
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
            elif route == "/api/doctor":
                self._send_json(self.server.backend.doctor())
            elif route == "/api/memories":
                include = _truthy(query.get("include_candidates", ["false"])[0])
                self._send_json(self.server.backend.list_memories(include_candidates=include))
            elif route == "/api/journal":
                raw_date = query.get("date", [None])[0]
                self._send_json(self.server.backend.read_journal(_parse_date(raw_date)))
            else:
                self._send_error(404, f"unknown route: {route}")
        except Exception as exc:
            self._send_error(500, str(exc))

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/") or "/"
            body = self._read_body()
            if route == "/api/bootstrap":
                self._send_json(self.server.backend.bootstrap(force=bool(body.get("force", False))))
            elif route == "/api/reflect":
                self._send_json(
                    self.server.backend.reflect(
                        text=str(body["text"]),
                        journal_date=_parse_date(body.get("date")),
                        source=str(body.get("source", "api")),
                        save_memory_candidates=bool(body.get("save_candidates", True)),
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
            elif route == "/api/daemon/tick":
                self._send_json(self.server.backend.daemon_tick())
            elif route == "/api/chat":
                self._send_json(
                    self.server.backend.chat_once(
                        text=str(body["text"]),
                        session=str(body.get("session", "default")),
                        autonomy=int(body.get("autonomy", 3)),
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
