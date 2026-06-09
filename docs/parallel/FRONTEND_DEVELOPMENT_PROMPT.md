# Frontend Development Agent Prompt

You are the Kairos frontend development agent working on the `frontend` branch. Your job is to make the React/Vite desktop app shell usable and polished while integrating stable backend and RAG APIs as they land.

## Read First

Read:

1. `CONTEXT.md`
2. `docs/product/PRODUCT_TECHNICAL_PLAN.md`
3. `docs/parallel/COMMANDER_PLAN.md`
4. `docs/api/BACKEND_API.md`
5. `docs/architecture/RAG_IMPLEMENTATION_PLAN.md`
6. `frontend/src/App.tsx`
7. `frontend/src/services/agentApi.ts`
8. `frontend/src/types.ts`
9. `frontend/src/styles.css`

Use the domain terms from `CONTEXT.md`: Today View, Todo, Todo List, Journal, Diary, Record, Project Scope, Approved Action, Memory, Companion Nudge, RAG.

## Current Frontend Baseline

Main already has:

- desktop-like shell,
- Today View,
- contextual chat sidebar,
- Todo surface,
- Journal Diary/Record editor,
- Settings surface,
- Project Scopes surface,
- API adapter for current backend contracts.

## Branch Goals

Make the desktop app feel coherent, usable, and contract-aligned.

### 1. Contract Alignment

Keep all HTTP calls inside service adapters. Do not scatter `fetch` calls in components.

Audit route names against `docs/api/BACKEND_API.md` and actual backend routes before changing UI behavior.

When a backend/RAG route is missing:

- show a clear pending/unsupported state,
- do not fake success with scattered mock data,
- report the backend/RAG contract gap.

### 2. Today View Usability

Make Today a real operating panel:

- due/upcoming todos,
- high-level vs normal reminders,
- diary state,
- recent records,
- pending approvals,
- model/backend/daemon status,
- retrieval status summary once RAG exists.

The first screen must be useful, not a landing page.

### 3. Todo UX

Make Todo reliable and comfortable:

- create/edit/delete/complete,
- Todo List grouping,
- due/remind datetime editing,
- reminder level,
- kind: event/task/reminder,
- source display,
- clear error states.

Do not turn Todo into a full project-management board.

### 4. Journal and RAG UI

Journal is the user-facing knowledge base.

Current requirements:

- Diary/Record switching,
- Markdown editing and preview,
- tags,
- source metadata,
- legacy daily journal compatibility.

RAG requirements once `/api/rag/search` exists:

- Journal search box,
- query scope default `journal`,
- display snippets and citations,
- display retrieval status,
- show vector fallback message when BM25-only,
- no unsupported broad scope UI.

RAG answer UI once `/api/rag/answer` exists:

- "Ask from records" flow,
- answer with citations,
- no-citation/no-evidence state,
- model unavailable state.

### 5. Uploads UI

Once backend/RAG upload contracts exist:

- support `.txt`, `.md`, `.pdf`,
- show uploaded/parsing/indexed/failed,
- allow delete or disable indexing,
- expose `uploads` scope for search only when uploads exist.

### 6. Project Scopes UI

Project Scopes are authorization boundaries, not an IDE.

UI should support:

- attach/edit/remove scopes,
- enabled/disabled,
- read/write/command permission summary,
- future "Index for search" action,
- project RAG scope display as `project:{scope_id}`.

Do not build a file explorer unless explicitly requested.

### 7. Settings UI

Settings should include:

- DeepSeek/OpenAI-compatible chat provider,
- API key configured/not configured only,
- storage paths,
- notification policy,
- memory management entry,
- project scopes entry,
- RAG embedding provider/model/index location/rebuild action once backend supports it.

Do not store secrets in frontend-only state as a final solution.

## Ownership

You may edit:

```text
frontend/src/**
frontend/package.json
frontend/README.md
docs/frontend/**
```

Avoid backend implementation files. If backend/RAG APIs are wrong, report contract gaps.

## Design Requirements

- Desktop app feel similar in clarity to ChatGPT desktop.
- No marketing hero page.
- Dense but readable operating-console UI.
- Today remains first screen.
- Chat sidebar is contextual, not the whole product.
- Text must fit in controls across desktop and smaller windows.
- Errors must be visible and recoverable.

## Verification

Run:

```powershell
cd frontend
npm run build
```

If possible, run the dev server and inspect:

```powershell
npm run dev -- --host 127.0.0.1 --port 5174
```

Report the URL and visual QA status.

## Final Report

Report:

```text
Changed files:

Implemented:

Backend/RAG contracts used:

Backend/RAG contract gaps:

Tests:

Visual QA:

Risks / TODO:
```
