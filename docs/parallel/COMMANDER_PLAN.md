# Kairos Parallel Development Commander Plan

This document is the current coordination contract for parallel Kairos development. Older Claude/Codex worker rounds are obsolete. Kairos is now a local-first personal work/life operating console with a desktop-app experience, reliable Todo, Journal/Record knowledge base, Project Scopes, Settings, and a planned local RAG retrieval layer.

## Required Reading

Every development agent must read:

1. `CONTEXT.md`
2. `docs/product/PRODUCT_TECHNICAL_PLAN.md`
3. `docs/architecture/RAG_IMPLEMENTATION_PLAN.md`
4. `docs/api/BACKEND_API.md`
5. this file
6. its branch-specific prompt

Branch-specific prompts:

```text
docs/parallel/BACKEND_DEVELOPMENT_PROMPT.md
docs/parallel/FRONTEND_DEVELOPMENT_PROMPT.md
docs/parallel/RAG_DEVELOPMENT_PROMPT.md
```

## Current Mainline Status

Main currently contains:

- FastAPI backend with `KairosBackend` service layer.
- React/Vite desktop-like app shell.
- Today View API and frontend surface.
- Todo and Todo List CRUD.
- reliable reminder bridge for Todo `remind_at`.
- Journal Diary/Record artifact APIs and frontend editor.
- Journal capture into Diary or Record.
- Settings API and frontend surface with DeepSeek/OpenAI-compatible configuration.
- Project Scope API and frontend surface.
- durable Approved Actions and approval endpoints.
- native tools including Todo tools and existing file/memory/search helpers.
- permission and audit pipeline through `ToolRouter`, `PermissionManager`, and `AuditLogger`.
- RAG architecture and product plan documents, but not the RAG implementation.

The latest verified baseline before this plan update:

```text
E:\software\Miniconda\python.exe -m pytest
67 passed

npm run build
passed
```

## Active Development Branches

Use three branches/worktrees:

```text
backend
frontend
rag
```

Recommended worktree layout:

```text
.worktree/backend
.worktree/frontend
.worktree/rag
```

Before starting work, each branch should merge or rebase from current `main`. Do not work from old branch bases.

## Ownership Boundaries

### Backend Branch

Owns product backend contracts outside RAG internals:

```text
backend/src/kairos/backend/**
backend/src/kairos/presence/**
backend/src/kairos/delivery/**
backend/src/kairos/channels/**
backend/src/kairos/settings-related code if added
docs/api/BACKEND_API.md
tests/test_backend_api.py
tests/test_fastapi_app.py
tests/test_presence_delivery.py
```

Backend may touch tools only when wiring product APIs to existing tool contracts. It should not implement the retrieval engine; that belongs to `rag`.

### Frontend Branch

Owns the desktop app UI and adapters:

```text
frontend/src/**
frontend/package.json
frontend/README.md
docs/frontend/**
```

Frontend should not modify backend implementation files. If an API contract is missing or inconsistent, report the contract gap or update frontend adapters only when the backend route already exists.

### RAG Branch

Owns local retrieval and evidence-based answer infrastructure:

```text
backend/src/kairos/retrieval/**
backend/src/kairos/tools/advanced.py or native registry wiring for rag tools
backend/src/kairos/backend/fastapi_app.py only for /api/rag routes
backend/src/kairos/backend/service.py only for thin RetrievalService delegation
backend/src/kairos/backend/settings.py only for RAG settings
docs/architecture/RAG_IMPLEMENTATION_PLAN.md
docs/api/BACKEND_API.md RAG sections
tests/test_rag_*.py
```

RAG must not bypass Project Scope permission checks, ToolRouter, PermissionManager, or AuditLogger.

## Shared Rules

1. Preserve the language in `CONTEXT.md`.
2. Keep user-facing durable knowledge in Journal/Record, not Memory.
3. Keep Memory as agent-facing context and candidate-gated.
4. Keep all agent-initiated tools behind `ToolRouter -> PermissionManager -> AuditLogger`.
5. Do not introduce LangChain, LangGraph, PostgreSQL, OpenSearch, Redis, or Airflow for the current RAG slice.
6. Do not make broad RAG scopes such as `all`, `*`, `filesystem`, `memory`, or `chat`.
7. Do not index out-of-scope files or sensitive files.
8. Do not write private runtime data into the repository.
9. Do not run whole-repo formatting.
10. Add tests for new contracts and keep existing tests green.

## Coordination Order

Recommended order:

1. `rag` implements `/api/rag/search` for `journal` scope and `rag.search` tool first.
2. `frontend` adds Journal search UI against `/api/rag/search` once the route exists.
3. `backend` continues non-RAG product hardening: approvals, settings, reminders, project-scope lifecycle, daemon/status polish.
4. `rag` adds Ollama embeddings and BM25 fallback.
5. `rag` adds `/api/rag/answer` and `rag.answer`.
6. `frontend` adds evidence answer UI, upload UI, and retrieval status/citation display.
7. `backend` and `rag` coordinate on Project Scope indexing and upload persistence.

Commander should merge in this order when possible:

```text
backend -> rag -> frontend
```

If frontend depends on new RAG or backend routes, merge those backend/RAG branches first.

## Merge Checklist

Before merging a branch:

- confirm the branch started from current enough `main`,
- inspect `git diff --name-only`,
- confirm files are inside branch ownership boundaries,
- run relevant tests,
- run full tests when backend or RAG changed,
- run frontend build when frontend changed,
- check API route names against `docs/api/BACKEND_API.md`,
- check frontend adapter paths against actual FastAPI routes,
- check no `.kairos/`, logs, local indexes, uploads, or worktree directories were staged.

Required final verification after all merges:

```powershell
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=(Resolve-Path .tmp).Path
$env:PYTEST_ADDOPTS='-p no:cacheprovider --basetemp=.tmp/pytest'
& 'E:\software\Miniconda\python.exe' -m pytest
```

```powershell
cd frontend
npm run build
```

## Final Report Format

Each branch agent must report:

```text
Changed files:
- ...

Implemented:
- ...

API/tool contracts:
- ...

Tests:
- command
- result

Contract gaps or merge notes:
- ...

Risks / TODO:
- ...
```

Commander final report should additionally include:

- current project progress,
- merged commits,
- verification results,
- remaining branch responsibilities,
- final acceptance status.
