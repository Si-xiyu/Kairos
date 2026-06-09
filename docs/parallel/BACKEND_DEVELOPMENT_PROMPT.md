# Backend Development Agent Prompt

You are the Kairos backend development agent working on the `backend` branch. Your job is to harden and complete the product backend around Today, Todo, Journal, Settings, Project Scopes, Approvals, daemon/reminders, and non-RAG runtime contracts.

Do not implement the RetrievalService internals; that belongs to the `rag` branch.

## Read First

Read:

1. `CONTEXT.md`
2. `docs/product/PRODUCT_TECHNICAL_PLAN.md`
3. `docs/parallel/COMMANDER_PLAN.md`
4. `docs/api/BACKEND_API.md`
5. `backend/src/kairos/backend/service.py`
6. `backend/src/kairos/backend/fastapi_app.py`
7. `backend/src/kairos/backend/todos.py`
8. `backend/src/kairos/backend/settings.py`
9. `backend/src/kairos/backend/scopes.py`
10. `backend/src/kairos/backend/approvals.py`

Use the domain terms from `CONTEXT.md`. Kairos is a Personal Operating Console, not a coding assistant.

## Current Backend Baseline

Main already has:

- `/api/today`
- Todo and Todo List CRUD
- Journal artifact CRUD
- Journal capture
- Settings API with DeepSeek/OpenAI-compatible config
- Project Scope API
- Approval API
- Todo proposal and approval flow
- Todo reminder bridge into delivery queue
- FastAPI and stdlib HTTP route surfaces

## Branch Goals

Make the current product backend reliable enough for a usable desktop app.

### 1. API Contract Consistency

Audit `docs/api/BACKEND_API.md`, `fastapi_app.py`, stdlib `http.py`, and frontend adapter expectations.

Fix mismatches in:

- route names,
- body id fields such as `id`, `todo_id`, `scope_id`, `artifact_id`,
- response shapes,
- error shape,
- journal artifact field names,
- settings response/write shape.

Do not rename established routes unless you also preserve compatibility aliases.

### 2. Approval Flow Hardening

Make Approved Actions useful beyond Todo proposal:

- list pending actions by status,
- approve/reject reliably,
- include action type, summary, payload, source, timestamps,
- expose pending count in Today,
- keep approval action results auditable.

Do not execute destructive or reliable actions without approval.

### 3. Todo and Reminder Reliability

Improve Todo behavior:

- prevent duplicate reminder delivery for the same Todo/remind_at,
- distinguish high-level and normal reminders in Today and delivery metadata,
- handle timezone-aware ISO datetimes consistently,
- keep manual frontend-created todos direct,
- keep agent-created reliable todos behind approval/tool flow.

### 4. Journal Product Polish

Keep Journal as the user-facing knowledge base:

- ensure Diary/Record artifact APIs are stable,
- ensure legacy daily journal routes still work,
- ensure Journal Capture creates curated summaries rather than raw transcripts,
- ensure capture responses are not mojibake,
- expose source metadata useful for future RAG indexing.

### 5. Settings and Project Scope Hardening

Settings:

- never return raw API keys,
- support DeepSeek defaults,
- expose storage, notification, memory review, project scopes,
- prepare fields for RAG settings without implementing retrieval internals.

Project Scopes:

- validate paths,
- support enabled/disabled state,
- expose permission summary,
- provide reusable permission checks for RAG and future file tools,
- avoid accidentally granting out-of-scope access.

### 6. Daemon and Status

Keep app status useful for Today:

- daemon status,
- delivery pending/failed,
- reminder due/upcoming,
- model/provider summary,
- approval pending count.

## Ownership

You may edit:

```text
backend/src/kairos/backend/**
backend/src/kairos/presence/**
backend/src/kairos/delivery/**
backend/src/kairos/channels/**
backend/src/kairos/tools/advanced.py only for non-RAG product tools
docs/api/BACKEND_API.md
tests/test_backend_api.py
tests/test_fastapi_app.py
tests/test_presence_delivery.py
```

Avoid:

- `backend/src/kairos/retrieval/**`
- frontend files
- large core AgentLoop rewrites
- new heavy dependencies

If you need a RAG contract, report it as a note for the `rag` branch.

## Verification

Run focused tests and full tests:

```powershell
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=(Resolve-Path .tmp).Path
$env:PYTEST_ADDOPTS='-p no:cacheprovider --basetemp=.tmp/pytest'
& 'E:\software\Miniconda\python.exe' -m pytest
```

Also run:

```powershell
git diff --check
```

## Final Report

Report:

```text
Changed files:

Implemented:

API/tool contracts:

Tests:

RAG/frontend contract notes:

Risks / TODO:
```
