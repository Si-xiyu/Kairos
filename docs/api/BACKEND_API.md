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
  "todos": {"available": true, "items": [], "due": [], "upcoming": [], "total_open": 0},
  "reminders": {"available": true, "total": 1, "enabled": 1, "due": 0, "high_level": [], "normal": [], "companion_nudges": [], "items": []},
  "recent_artifacts": [],
  "recent_sessions": [],
  "memory": {"pending_candidates": 0, "available": true},
  "approvals": {"available": true, "pending": 0, "actions": []},
  "delivery": {"pending": 0, "failed": 0},
  "daemon": {"available": true, "heartbeat_session_id": "kairos-presence", "presence_events": 0},
  "model": {"provider": "local", "suggested_provider": "deepseek", "model": "kairos-local-mvp"}
}
```

Today includes `todos.due`, `todos.upcoming`, `reminders.high_level`, and `reminders.normal` so the frontend can distinguish dependable High-Level Reminders from ordinary reminders.

## Settings

```text
GET /api/settings
POST /api/settings
```

Settings exposes DeepSeek-oriented OpenAI-compatible provider configuration, storage paths, notification policy, and entry points for Memory review and Project Scopes.

Example response:

```json
{
  "llm": {
    "provider": "openai-compatible",
    "suggested_provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "timeout": 60,
    "api_key_configured": true,
    "api_key_preview": "configured"
  },
  "storage": {
    "kairos_home": ".kairos",
    "journal_path": ".kairos/journal",
    "record_path": ".kairos/journal/artifacts"
  },
  "notifications": {
    "enabled": true,
    "high_level_enabled": true,
    "companion_nudges_enabled": true,
    "quiet_hours_start": "23:00",
    "quiet_hours_end": "08:00",
    "daily_notification_budget": 3,
    "default_channel": "windows_toast"
  },
  "memory_review": {"available": true, "href": "/api/memories?include_candidates=true"},
  "project_scopes": {"available": true, "href": "/api/project-scopes"}
}
```

`POST /api/settings` accepts partial `llm`, `storage`, and `notifications` objects. LLM writes also update `.kairos/llm.json`, which is read by the existing provider loader. API keys may be provided on write, but settings responses never include raw API key values.

## Project Scopes

```text
GET /api/project-scopes
POST /api/project-scopes
POST /api/project-scopes/update
POST /api/project-scopes/delete
```

Project Scope fields:

```json
{
  "id": "scope-abc123",
  "name": "Kairos Backend",
  "path": "E:\\Code\\Kairos",
  "permissions": {"read": true, "write": false, "command": false},
  "permission_summary": "read",
  "enabled": true,
  "created_at": "...",
  "updated_at": "..."
}
```

The backend also exposes a reusable `ProjectScopeStore.scope_for_path(path, permission)` interface for future file tools to check Scope Permission before local file work.

## Approved Actions

```text
GET /api/approvals?status=pending
POST /api/approvals/approve
POST /api/approvals/reject
```

Approved Action fields:

```json
{
  "id": "approval-abc123",
  "action_type": "todo.create",
  "title": "Create todo: Submit report",
  "summary": "Submit report | remind at 2026-06-05T09:00:00+00:00",
  "payload": {"tool": "todo.create", "arguments": {"title": "Submit report"}},
  "status": "pending",
  "source": "chat",
  "created_at": "...",
  "updated_at": "..."
}
```

`todo.propose` creates a pending Approved Action instead of saving a reliable Todo immediately. Approving a `todo.create` action creates the Todo.

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

When an open Todo has a past `remind_at` and `reminder_level` is `high` or `normal`, backend Todo creation/update and `POST /api/daemon/tick` enqueue it into the delivery queue once. High-Level Reminders use `reminder_level: "high"`; ordinary reminders use `"normal"`.

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
POST /api/journal/capture
```

Default capture heading:

```text
有价值的对话
```

Journal capture stores structured summary fields rather than copying raw transcript text. `type: "diary"` appends to the daily Diary; `type: "record"` creates a Record artifact. Responses include `message: "已加入日记"` or `message: "已加入记录"`.

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

Capabilities expose native tools, skill manifests, and MCP/plugin manifests. Native tools include file, memory, web/weather/location, meal recommendation, Todo tools, and `journal.capture`.

## Static Frontend

`python app.py` checks common frontend output folders such as `frontend/dist`, `frontend/build`, `web/dist`, `web/build`, and `public`. If an `index.html` exists, non-API routes serve the frontend. Otherwise `/` returns a small JSON backend status response.
