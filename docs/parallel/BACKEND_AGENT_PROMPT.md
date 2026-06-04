# Backend Agent Prompt

You are the Kairos backend implementation agent. Your job is to turn the current tested backend scaffold into the backend for a usable local-first personal operating console. Kairos is not primarily a coding assistant; coding mode is only a strong local file-work mode inside authorized project scopes.

## Read First

Read these files before editing:

1. `CONTEXT.md`
2. `docs/product/PRODUCT_TECHNICAL_PLAN.md`
3. `docs/api/BACKEND_API.md`
4. `docs/adr/0001-commander-core-contracts.md`
5. `docs/adr/0003-single-step-lifelog-presence-workflows.md`
6. `docs/adr/0004-markdown-journal-knowledge-base.md`
7. `README.md`

Treat `CONTEXT.md` as the domain language source of truth. Use these terms exactly: Personal Operating Console, Today View, Todo, Todo List, Diary, Record, Journal Capture, Memory, Project Scope, Approved Action, Scope Permission, Companion Nudge.

## Product Goal

Build the backend surface needed for a ChatGPT-like desktop app with:

- Today as the home surface,
- a reliable Todo system,
- Journal as the user-facing Markdown knowledge base,
- Memory as agent-facing context,
- Project Scopes as local file permission boundaries,
- DeepSeek as the near-term default API target through the existing OpenAI-compatible provider boundary,
- all meaningful actions flowing through the tool/permission/audit pipeline when they are agent-initiated.

## Primary Backend Deliverables

Implement the next backend slice in this order.

### 1. Fix User-Visible Mojibake

Find and replace corrupted user-facing Chinese strings in backend code and API docs. Keep internal identifiers stable. Focus on reminders, journal headings, weekly review section titles, model error messages, and examples.

Do not rewrite unrelated prose or change API route names while doing this.

### 2. Today API

Add or extend a backend endpoint that gives the frontend a single Today View payload. Prefer `GET /api/today` if it does not exist yet.

The response should compose existing data where possible:

- today's date,
- diary state,
- due or upcoming todos,
- high-level reminder state,
- recent diary/record artifacts,
- recent chat sessions,
- pending memory candidates count,
- pending approval/action count if available,
- delivery/daemon/heartbeat status,
- model/provider status.

If some sections are not implemented yet, return empty arrays or explicit `available: false` fields rather than making the frontend guess.

### 3. Todo MVP

Add a compact reliable Todo system. It is not a full project-management board.

Minimum domain fields:

- `id`
- `title`
- `notes`
- `kind`: `event | task | reminder`
- `list_id`
- `status`: `open | completed`
- `due_at`
- `remind_at`
- `reminder_level`: `high | normal | none`
- `source`: `manual | kairos | chat`
- `source_ref`
- `created_at`
- `updated_at`

Todo List fields:

- `id`
- `name`
- `created_at`
- `updated_at`

Storage can be JSON for the first slice if that matches the current repo style; SQLite can wait unless the repo already has a clear SQLite pattern. Keep tests deterministic and do not write outside the configured Kairos root.

Required API surface:

- `GET /api/todos`
- `POST /api/todos`
- `POST /api/todos/update`
- `POST /api/todos/delete`
- `POST /api/todos/complete`
- `GET /api/todo-lists`
- `POST /api/todo-lists`
- `POST /api/todo-lists/update`
- `POST /api/todo-lists/delete`

Agent-created todos must be represented as proposed or require an approval/confirmation step before becoming reliable reminders. Manual frontend-created todos can be saved directly.

### 4. Todo Tool Calls

Expose native tools for Kairos to propose or create todos through the shared registry. Use the existing permission model and audit path.

Recommended tool names:

- `todo.propose`
- `todo.create`
- `todo.update`
- `todo.complete`
- `todo.delete`

Risk guidance:

- proposing a todo: low risk,
- creating a reliable todo/reminder from chat: medium risk or requires confirmation,
- deleting todos: medium risk,
- changing high-level reminder timing: medium risk.

Do not bypass `ToolRouter`, `PermissionManager`, or `AuditLogger`.

### 5. Journal Knowledge Base Foundation

Add a Markdown + YAML front matter foundation for Journal artifacts if it does not exist yet.

Artifact categories:

- `diary`
- `record`

Minimum front matter:

```yaml
---
type: diary | record
title: string
created_at: ISO datetime
updated_at: ISO datetime
tags: []
source:
  kind: chat | manual | import | kairos
  session_id: string | null
---
```

Diary artifacts also include:

```yaml
date: YYYY-MM-DD
```

Records may include:

```yaml
summary: string
```

Required API surface can be minimal for this slice:

- `GET /api/journal/artifacts`
- `GET /api/journal/artifacts/{id}`
- `POST /api/journal/artifacts`
- `POST /api/journal/artifacts/update`
- `POST /api/journal/artifacts/delete`

If route conflicts with existing journal routes, preserve existing compatibility and add the new routes alongside them.

### 6. DeepSeek-Oriented Provider Defaults

Keep the provider OpenAI-compatible. Add DeepSeek-friendly defaults in config/docs where appropriate, without hard-coding secrets:

- default base URL can point to DeepSeek only when provider is explicitly configured,
- Settings/frontends should be able to show DeepSeek as the primary suggested provider,
- existing env/json config precedence must continue working.

## Backend Boundaries

You may edit:

- `backend/src/kairos/backend/**`
- `backend/src/kairos/lifelog/**`
- `backend/src/kairos/memory/**`
- `backend/src/kairos/presence/**`
- `backend/src/kairos/delivery/**`
- `backend/src/kairos/tools/**`
- `backend/src/kairos/config.py`
- `backend/src/kairos/llm*.py`
- `backend/src/kairos/cli.py`
- `tests/**`
- `docs/api/BACKEND_API.md`
- backend-relevant docs when needed

Avoid large frontend edits. If you must request a frontend contract change, write it in your final report instead of modifying frontend code.

Do not introduce new dependencies unless the benefit is clear and you update `pyproject.toml` plus tests. Prefer standard library parsers/writers for the first slice.

## Compatibility Requirements

- Preserve current FastAPI route compatibility.
- Preserve `python app.py --root . --host 127.0.0.1 --port 8765`.
- Preserve existing CLI smoke workflows unless intentionally extended.
- Do not silently change `.kairos/` existing storage paths without migration or compatibility.
- Do not treat Memory as the user's knowledge base; Journal is the user-facing knowledge base.
- Do not promote candidate memory automatically.

## Verification

Run backend tests with a workspace-local pytest temp directory if Windows Temp is inaccessible:

```powershell
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=(Resolve-Path .tmp).Path
$env:PYTEST_ADDOPTS='-p no:cacheprovider --basetemp=.tmp/pytest'
python -m pytest
```

Also run focused tests you add or change.

## Final Report Format

Use this structure:

```text
Changed files:
- ...

Implemented:
- ...

API changes:
- ...

Tests:
- command
- result

Frontend contract notes:
- ...

Risks / TODO:
- ...
```
