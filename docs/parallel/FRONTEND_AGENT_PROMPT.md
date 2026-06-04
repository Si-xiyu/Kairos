# Frontend Agent Prompt

You are the Kairos frontend implementation agent. Your job is to turn the current React/Vite console into a usable local desktop-app-style interface. The target feel is similar to a ChatGPT desktop app, but Kairos is not chat-only: it is a personal work/life operating console with Today, Todo, Journal, Project Scopes, Settings, and a contextual chat sidebar.

## Read First

Read these files before editing:

1. `CONTEXT.md`
2. `docs/product/PRODUCT_TECHNICAL_PLAN.md`
3. `docs/api/BACKEND_API.md`
4. `docs/adr/0004-markdown-journal-knowledge-base.md`
5. `frontend/src/App.tsx`
6. `frontend/src/services/agentApi.ts`
7. `frontend/src/types.ts`
8. `frontend/src/styles.css`

Treat `CONTEXT.md` as the domain language source of truth. Use these terms exactly: Today View, Todo, Todo List, Diary, Record, Journal Capture, Memory, Project Scope, Approved Action, Scope Permission, Companion Nudge.

## Product Goal

Build the first desktop-like app shell:

- persistent left navigation,
- Today as the home surface,
- contextual chat sidebar available across views,
- Todo as a reliable editable reminder system,
- Journal as the user-facing Markdown knowledge base,
- Settings as the place for model/storage/notifications/memory/project-scope configuration,
- Project Scopes as directory authorization boundaries, not an IDE.

The app should feel like an everyday personal console, not a backend demo or a marketing landing page.

## Primary Frontend Deliverables

Implement the next frontend slice in this order.

### 1. App Shell

Replace the chat-only layout with a desktop app shell:

- left navigation,
- central view outlet,
- right or collapsible contextual chat sidebar,
- top/status area for backend/model/daemon state,
- secondary inspector/activity panel only where useful.

Primary nav items:

- Today
- Todo
- Journal
- Project Scopes
- Settings
- Chat, either as an expandable full view or sidebar control

Do not make a landing page. The first screen should be the usable Today View.

### 2. Today View

Create a Today View that uses backend state and degrades gracefully if newer endpoints are unavailable.

Show:

- today's date,
- due/upcoming todos,
- diary status,
- recent records or journals,
- recent sessions,
- pending approvals or memory candidates if available,
- backend/model/daemon status,
- low-level companion nudge area if available.

If `GET /api/today` exists, use it. Until then, compose from existing endpoints such as `/api/state`, `/api/sessions`, `/api/journals`, `/api/schedules`.

### 3. Contextual Chat Sidebar

Keep the existing chat functionality but make it contextual:

- active view should influence visible placeholder text and metadata sent to the backend when supported,
- Today chat should feel like acting on today,
- Todo chat should help create or update todos,
- Journal chat should help summarize or archive,
- Project Scopes chat should be the place where local file work is framed.

Do not make chat consume the whole app by default.

### 4. Todo View

Build a compact todo UI similar in spirit to iOS Reminders basics:

- list sidebar or segmented list filter,
- todo list group support,
- create/edit/delete/complete,
- due time,
- reminder time,
- reminder level: high, normal, none,
- kind: event, task, reminder,
- source display when provided by backend.

Use backend todo endpoints if available:

- `GET /api/todos`
- `POST /api/todos`
- `POST /api/todos/update`
- `POST /api/todos/delete`
- `POST /api/todos/complete`
- `GET /api/todo-lists`
- list CRUD endpoints

If endpoints are not available yet, isolate temporary empty-state/mock behavior in the API adapter and make the missing backend contract explicit in your final report. Do not scatter mock data across components.

Agent-created todos from chat should appear as confirmation cards when the backend exposes them. Manual user-created todos can save directly.

### 5. Journal View

Build the first Journal UI around two categories:

- Diary
- Record

Use Markdown-oriented UI assumptions:

- title,
- date for diary,
- tags from YAML front matter,
- source link when available,
- editor or readable preview.

If the new artifact endpoints are not available yet, use existing `/api/journals` and `/api/journal` for diary-like content and show records as an empty state. Keep the API adapter clean so backend endpoints can replace it.

### 6. Settings View

Implement a minimal Settings surface:

- model provider card with DeepSeek as the near-term default target,
- API base URL / model / key placeholder fields,
- storage location summary,
- notification policy placeholders,
- memory management entry point,
- project scope entry point,
- MCP/search/weather provider placeholders.

Do not store secrets in frontend-only local state as a final solution. If backend settings endpoints do not exist, make the UI read-only or clearly pending.

### 7. Project Scopes View

Build a simple authorization-boundary UI, not an IDE:

- list attached scopes,
- show directory path,
- show read/write/command permission summary,
- add/remove/edit buttons can be disabled or call backend when available,
- explain through concise UI labels that scope controls where Kairos may work.

Do not build a full file explorer unless the backend contract already supports it.

## Frontend Boundaries

You may edit:

- `frontend/src/**`
- `frontend/package.json` only if a dependency is truly needed
- `frontend/README.md`
- `docs/frontend/**`
- frontend-relevant API notes

Avoid backend edits. If the backend endpoint you need is missing, update the API adapter with a controlled fallback and report the required backend contract.

Do not introduce a heavy UI framework unless explicitly justified. Prefer the existing React/Vite/TypeScript setup. Use accessible HTML controls and keep styling professional, dense, and app-like.

## Design Requirements

- Desktop app feel, not a marketing site.
- ChatGPT-like clarity and immediacy, but with Kairos-specific navigation.
- No giant hero section.
- No decorative card soup.
- Today is the first usable screen.
- Keep cards for repeated items and panels, not every page section.
- Text must fit on desktop and smaller windows.
- Use clear controls for todos and settings.
- Avoid single-hue visual themes; keep the UI quiet, readable, and work-focused.

## API Adapter Rules

Keep all backend calls in `frontend/src/services/agentApi.ts` or a small set of service modules.

Use typed response shapes. Components should not construct raw fetch calls.

Fallback behavior should be explicit:

- backend unavailable: show offline state,
- endpoint unavailable: show empty state and report contract gap,
- request failed: show recoverable error.

## Verification

Run:

```powershell
npm run build
```

If you start a dev server, report the local URL. If browser testing is available, inspect the app at desktop width and verify that Today, Todo, Journal, Settings, Project Scopes, and chat sidebar do not overlap.

## Final Report Format

Use this structure:

```text
Changed files:
- ...

Implemented:
- ...

Backend contract used:
- ...

Backend contract gaps:
- ...

Tests:
- command
- result

Risks / TODO:
- ...
```
