# Kairos Backend API

Start the backend from the repository root:

```text
python app.py --root . --host 127.0.0.1 --port 8765
```

The backend returns JSON, enables permissive CORS for local frontend development, and preserves the existing route surface.

Base URL:

```text
http://127.0.0.1:8765
```

## Health

```text
GET /api/health
```

```json
{"ok": true, "service": "kairos"}
```

## Bootstrap

```text
POST /api/bootstrap
```

Body:

```json
{"force": false}
```

Creates `.kairos/` and installs the default nightly diary reminder:

```text
今天还没有留下记录。要不要随手丢几个碎片给我，我帮你整理成日记？
```

## Doctor

```text
GET /api/doctor
```

Returns local workspace counts for conversations, journals, memory, schedules, delivery, and audit events.

## Application State

```text
GET /api/state
```

Returns the existing frontend-friendly snapshot. The `today` field remains compact for compatibility. Use `GET /api/today` for the full Today View payload.

## Today View

```text
GET /api/today
```

Returns a single payload for the Today View:

```json
{
  "date": "2026-06-04",
  "diary": {"date": "2026-06-04", "exists": false, "path": "...", "available": true},
  "todos": {"available": true, "items": [], "total_open": 0},
  "reminders": {"available": true, "total": 1, "enabled": 1, "due": 0, "items": []},
  "recent_artifacts": [],
  "recent_sessions": [],
  "memory": {"pending_candidates": 0, "available": true},
  "approvals": {"available": false, "pending": 0},
  "delivery": {"pending": 0, "failed": 0},
  "daemon": {"available": true, "heartbeat_session_id": "kairos-presence", "presence_events": 0},
  "model": {"provider": "local", "suggested_provider": "deepseek", "model": "kairos-local-mvp"}
}
```

Sections that are not yet backed by durable state use explicit `available: false` fields rather than requiring frontend guesses.

## Sessions

```text
GET /api/sessions?limit=50
POST /api/sessions
GET /api/sessions/{id}
GET /api/sessions/{id}/messages
GET /api/sessions/{id}/events
```

Messages are normalized into `{id, sessionId, role, author, createdAt, status, blocks}`. Events are normalized for the frontend Agent Inspector.

## Chat Once

```text
POST /api/chat
```

Body:

```json
{"text": "/tool file.list path=.", "session": "default", "autonomy": 3}
```

Runs one `AgentLoop` turn. Slash-command tools and model tool calls execute through the permission-gated `ToolRouter` and audit log.

## Todo

Todo fields:

```json
{
  "id": "todo-abc123",
  "title": "Submit backend API",
  "notes": "",
  "kind": "task",
  "list_id": "inbox",
  "status": "open",
  "due_at": "2026-06-04T12:00:00+00:00",
  "remind_at": null,
  "reminder_level": "normal",
  "source": "manual",
  "source_ref": null,
  "created_at": "...",
  "updated_at": "..."
}
```

Routes:

```text
GET /api/todos
POST /api/todos
POST /api/todos/update
POST /api/todos/delete
POST /api/todos/complete
GET /api/todo-lists
POST /api/todo-lists
POST /api/todo-lists/update
POST /api/todo-lists/delete
```

`POST /api/todos` accepts the Todo fields above except timestamps. Manual frontend-created todos can be saved directly. Agent-created reliable todos should go through the tool/permission path.

Todo tools:

```text
todo.propose
todo.create
todo.update
todo.complete
todo.delete
```

`todo.propose` is low risk and returns a proposed todo without saving. Creating, updating, completing, and deleting reliable todos are medium risk and pass through `ToolRouter`, `PermissionManager`, and `AuditLogger`.

## Journal

Legacy daily journal routes remain supported:

```text
GET /api/journal?date=2026-05-16
GET /api/journals?limit=30
POST /api/journal
POST /api/journal/append
POST /api/journal/capture-session
```

Default capture heading:

```text
有价值的对话
```

## Journal Artifacts

Journal artifacts are Markdown files with YAML front matter. Built-in categories are `diary` and `record`.

Required front matter:

```yaml
---
type: diary
title: Daily note
created_at: 2026-06-04T12:00:00+00:00
updated_at: 2026-06-04T12:00:00+00:00
tags: []
source:
  kind: manual
  session_id: null
date: 2026-06-04
---
```

Routes:

```text
GET /api/journal/artifacts?type=diary&limit=50
GET /api/journal/artifacts/{id}
POST /api/journal/artifacts
POST /api/journal/artifacts/update
POST /api/journal/artifacts/delete
```

Create body:

```json
{
  "type": "record",
  "title": "Backend slice",
  "summary": "Today, Todo, Journal artifact",
  "tags": ["kairos"],
  "source": {"kind": "manual", "session_id": null},
  "body": "实现后端可用切片。"
}
```

## Memories

```text
GET /api/memories?include_candidates=true
POST /api/memories
POST /api/memories/confirm
POST /api/memories/update
POST /api/memories/delete
```

Memory remains agent-facing context. Candidate memories are not promoted automatically.

## Schedule, Daemon, Heartbeat

```text
GET /api/schedules
POST /api/schedules
POST /api/schedules/toggle
POST /api/schedules/delete
POST /api/daemon/tick
GET /api/daemon/status
POST /api/daemon/start
POST /api/daemon/stop
POST /api/heartbeat/tick
```

Schedule example:

```json
{
  "id": "demo",
  "name": "Demo Reminder",
  "kind": "every",
  "seconds": 3600,
  "event": "daily_journal_check",
  "message": "要写日记吗？",
  "due_now": true
}
```

## Model Provider

Kairos defaults to a deterministic local fallback provider.

To connect an OpenAI-compatible endpoint, configure:

```text
KAIROS_LLM_PROVIDER=openai-compatible
KAIROS_LLM_BASE_URL=https://api.deepseek.com/v1
KAIROS_LLM_API_KEY=...
KAIROS_LLM_MODEL=deepseek-chat
KAIROS_LLM_TIMEOUT=60
```

Precedence is process environment, `.env`, JSON config, then built-in defaults. When `KAIROS_LLM_PROVIDER=openai-compatible` is explicit and no base URL/model is supplied, Kairos uses DeepSeek-friendly defaults without hard-coding secrets.

## Capabilities

```text
GET /api/capabilities
GET /api/skills
GET /api/skills/{name}
```

Capabilities expose native tools, skill manifests, and MCP/plugin manifests. Native tools include file, memory, web/weather/location, meal recommendation, and Todo tools.

## Static Frontend

`python app.py` checks common frontend output folders such as `frontend/dist`, `frontend/build`, `web/dist`, `web/build`, and `public`. If an `index.html` exists, non-API routes serve the frontend. Otherwise `/` returns a small JSON backend status response.
