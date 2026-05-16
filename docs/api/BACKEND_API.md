# Kairos Backend API

Start the backend from the repository root:

```text
python app.py --root . --host 127.0.0.1 --port 8765
```

The backend uses only Python standard library HTTP serving for the first MVP. It returns JSON and enables permissive CORS for local frontend development.

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

## Memories

```text
GET /api/memories?include_candidates=true
```

Returns confirmed memories and, when requested, candidate memories.

## Schedule

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

