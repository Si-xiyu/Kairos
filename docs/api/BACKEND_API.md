# Kairos Backend API

Start the backend from the repository root:

```text
python app.py --root . --host 127.0.0.1 --port 8765
```

The backend runs FastAPI through Uvicorn. It returns JSON and enables permissive CORS for local frontend development.

Base URL:

```text
http://127.0.0.1:8765
```

## Health

```text
GET /api/health
```

Response:

```json
{
  "ok": true,
  "service": "kairos"
}
```

## Bootstrap

```text
POST /api/bootstrap
```

Body:

```json
{
  "force": false
}
```

Creates `.kairos/` and installs the default nightly journal reminder.

## Doctor

```text
GET /api/doctor
```

Returns local workspace counts:

```json
{
  "initialized": true,
  "journals": 1,
  "memory_candidates": 2,
  "schedules": 1
}
```

## Application State

```text
GET /api/state
```

Returns one frontend-friendly snapshot:

```json
{
  "app": {"name": "Kairos", "mode": "local-first-backend"},
  "doctor": {},
  "today": {"date": "2026-05-16", "journal_exists": true},
  "recent_journals": [],
  "memories": {"confirmed": 1, "candidates": 0, "total": 1},
  "schedules": {"total": 1, "enabled": 1, "due": 0, "items": []},
  "delivery": {"pending": 0, "failed": 0},
  "capabilities": {"tools": 3, "skills": 0, "mcp_plugins": 0}
}
```

## Sessions

These routes adapt Kairos JSONL conversation logs to the current React frontend shape.

```text
GET /api/sessions?limit=50
```

Returns:

```json
{
  "sessions": [
    {
      "id": "default",
      "title": "Default",
      "summary": "Recent user message...",
      "updatedAt": "2026-05-16T12:00:00+00:00",
      "unreadCount": 0,
      "status": "active"
    }
  ]
}
```

```text
POST /api/sessions
```

Body:

```json
{
  "id": "session-ui",
  "title": "UI integration",
  "summary": "Frontend adapter smoke session."
}
```

```text
GET /api/sessions/{id}/messages
GET /api/sessions/{id}/events
```

Messages are normalized into `{id, sessionId, role, author, createdAt, status, blocks}`.

Events are normalized for the frontend Agent Inspector into `{id, sessionId, kind, title, timestamp, status, summary, details}`.

## Reflect

```text
POST /api/reflect
```

Body:

```json
{
  "text": "我喜欢先讨论架构，今天很有能量",
  "date": "2026-05-16",
  "source": "frontend",
  "save_candidates": true
}
```

Writes a daily journal and optionally saves memory candidates.

The response includes extracted candidate summaries:

```json
{
  "candidates": [
    {
      "name": "prefer_2026-05-16",
      "description": "User preference candidate from reflection draft.",
      "type": "user",
      "reason": "Positive preference keywords detected",
      "source": "journal/2026-05-16"
    }
  ]
}
```

## Journal

```text
GET /api/journal?date=2026-05-16
```

Returns:

```json
{
  "date": "2026-05-16",
  "path": "...",
  "exists": true,
  "content": "# 2026-05-16\n..."
}
```

```text
GET /api/journals?limit=30
```

Lists journal files, newest first.

```text
POST /api/journal
```

Body:

```json
{
  "date": "2026-05-16",
  "content": "# 2026-05-16\n\n## 今天发生了什么\n\n..."
}
```

```text
POST /api/journal/append
```

Body:

```json
{
  "date": "2026-05-16",
  "heading": "有价值的对话",
  "text": "今天和 Kairos 梳理了第一轮后端。"
}
```

```text
POST /api/journal/capture-session
```

Copies a JSONL conversation into a daily Markdown journal section.

Body:

```json
{
  "date": "2026-05-16",
  "session": "daily-chat",
  "heading": "有价值的对话",
  "include_roles": ["user", "assistant"]
}
```

Returns the updated journal plus:

```json
{
  "captured": 2,
  "session_id": "daily-chat"
}
```

## Memories

```text
GET /api/memories?include_candidates=true
```

Returns confirmed memories and, when requested, candidate memories.

Memory entries include candidate review fields:

```json
{
  "candidate": true,
  "candidate_reason": "Positive preference keywords detected",
  "source": "journal/2026-05-16",
  "source_journal_date": "2026-05-16"
}
```

```text
POST /api/memories
```

Creates a confirmed memory or a candidate:

```json
{
  "name": "prefers_architecture_first",
  "description": "User likes discussing architecture before implementation.",
  "type": "user",
  "scope": "private",
  "confidence": 0.7,
  "candidate": false,
  "content": "用户喜欢先讨论架构，再进入实现。"
}
```

```text
POST /api/memories/confirm
POST /api/memories/update
POST /api/memories/delete
```

Confirm body:

```json
{"name": "prefers_architecture_first"}
```

Delete body:

```json
{"name": "prefers_architecture_first", "candidate": false}
```

## Schedule

```text
GET /api/schedules
```

Lists all scheduled jobs.

```text
POST /api/schedules
```

Body:

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

Supported `kind` values for the frontend MVP:

- `every`
- `at`

For `at`, pass an ISO datetime in `at`, unless `due_now` is true.

```text
POST /api/schedules/toggle
POST /api/schedules/delete
```

Toggle body:

```json
{"id": "demo", "enabled": false}
```

## Daemon Tick

```text
POST /api/daemon/tick
```

Runs one synchronous scheduler/delivery tick. This is not a long-running daemon yet.

## Chat Once

```text
POST /api/chat
```

Body:

```json
{
  "text": "/tool file.list path=.",
  "session": "default",
  "autonomy": 3
}
```

Runs one deterministic `AgentLoop` turn. This does not call an LLM yet.

## Weekly Review

```text
POST /api/reviews/weekly
```

Body:

```json
{
  "start_date": "2026-05-10",
  "end_date": "2026-05-16"
}
```

Creates a Markdown weekly review draft from existing daily journals.

The response also returns the generated section bullets for frontend preview:

```json
{
  "sections": {
    "这一周你做了什么": ["2026-05-16: 实现 FastAPI 后端"],
    "哪些事情给你能量": ["2026-05-16: 架构讨论有能量"],
    "哪些事情反复消耗你": ["2026-05-16: 前端同步反复消耗"],
    "下周可以调整什么": ["优先减少反复消耗项，为深度工作留出连续时间。"]
  }
}
```

## Capabilities

```text
GET /api/capabilities
GET /api/skills
GET /api/skills/{name}
```

Capabilities exposes:

- native tools,
- skill manifests discovered from `skills/**/SKILL.md` and `.kairos/skills/**/SKILL.md`,
- MCP/plugin manifests discovered from known local plugin locations.

MCP/plugin manifests are discovery-only in this round. Live MCP transport comes later, and must still route through the shared permission layer.

## Static Frontend

`python app.py` also checks common frontend output folders such as `frontend/dist`, `frontend/build`, `web/dist`, `web/build`, and `public`.

If an `index.html` exists there, non-API routes serve the frontend. Otherwise `/` returns a small JSON backend status response.
