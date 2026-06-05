# Frontend Usable Shell Report - 2026-06-05

## Changed Files

- `frontend/src/App.tsx`
- `frontend/src/services/agentApi.ts`
- `frontend/src/styles.css`
- `frontend/src/types.ts`

## Implemented

- Today View now calls `GET /api/today` and displays real Today payload fields when available: todos, Journal artifacts, daemon/model state, pending approvals, recent sessions, and Companion Nudge text.
- Todo View uses real Todo CRUD adapter calls for create, update, delete, and complete. It supports Todo List grouping, list filtering, due time, reminder time, reminder level, kind, notes, and source.
- Journal View supports Diary / Record switching, tags editing, Markdown editing, Markdown preview, and New Record creation through artifact endpoints. Legacy daily journals remain visible and editable when artifact endpoints are unavailable.
- Settings View uses real Settings API reads/saves. DeepSeek provider fields, API base URL, model, storage path, notification policy, and memory entry are shown. Secret fields only show configured/not configured state and never echo a saved key value.
- Project Scopes View uses real API calls for add, permission-summary editing, enable/disable, and delete. It stays focused on directory authorization boundaries and does not add an IDE or file explorer.
- Error states are now surfaced in the relevant view instead of scattered mock behavior.

## Backend Contract Used

- `GET /api/today`
- `GET /api/todos`
- `POST /api/todos`
- `POST /api/todos/update`
- `POST /api/todos/delete`
- `POST /api/todos/complete`
- `GET /api/todo-lists`
- `GET /api/journal-artifacts?kind=diary|record`
- `GET /api/journal-artifacts/{id}`
- `POST /api/journal-artifacts`
- `POST /api/journal-artifacts/update`
- `GET /api/settings`
- `POST /api/settings`
- `GET /api/project-scopes`
- `POST /api/project-scopes`
- `POST /api/project-scopes/update`
- `POST /api/project-scopes/delete`
- Legacy compatibility: `GET /api/journals`, `GET /api/journal`, `POST /api/journal`

## Backend Contract Gaps Observed

The current backend branch does not expose `/api/today`, Todo CRUD, Todo List, Journal artifact, Settings, or Project Scope routes. The frontend now calls those contracts and shows clear per-view errors when the backend returns 404. Legacy daily Journal routes still work as the compatibility path.

## Tests

- `npm.cmd run build`
- Result: pass. TypeScript build and Vite production build completed.
- Dev server: `http://127.0.0.1:5173`
- Result: HTTP 200 from Vite dev server.

## Browser / Visual QA

- In-app browser QA could not be completed because the Browser plugin's required Node REPL `js` tool was not exposed in this session. Tool discovery returned unrelated connector tools.
- Local Playwright/Puppeteer were not installed in `frontend/node_modules`, so there was no fallback browser automation available without adding dependencies.
- Static responsive changes were made for desktop and small-window layouts: chat sidebar collapses below 940px, Today content remains in the main outlet, form controls wrap, and Todo/Journal/Project Scope controls use stable grid/flex dimensions.

## Risks / TODO

- Validate screenshots once the Browser `node_repl` tool or Playwright is available.
- Backend needs to implement the new contracts for Today, Todo, Journal artifacts, Settings, and Project Scopes for full end-to-end behavior.
