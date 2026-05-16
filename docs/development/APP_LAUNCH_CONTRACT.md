# App Launch Contract

Kairos is moving toward this product path:

```text
FastAPI backend -> React/Vite frontend -> Electron shell -> PyInstaller + electron-builder -> Windows installer
```

This document defines the process and URL contract so backend, frontend, and packaging work stay aligned.

## Development Mode

Run the backend:

```powershell
cd E:\Code\Kairos
python app.py --host 127.0.0.1 --port 8765 --root .
```

Backend base URL:

```text
http://127.0.0.1:8765
```

Run the frontend:

```powershell
cd E:\Code\Kairos-frontend\frontend
npm install
npm run dev
```

Vite dev URL:

```text
http://127.0.0.1:5173
```

Electron development shell should load:

```text
http://127.0.0.1:5173
```

The frontend should call the backend through:

```text
http://127.0.0.1:8765
```

The backend currently allows permissive CORS for local development.

## Frontend API Base

The frontend should centralize API calls in:

```text
frontend/src/services/agentApi.ts
```

Recommended base URL resolution:

```text
VITE_KAIROS_API_BASE ?? http://127.0.0.1:8765
```

Do not hard-code production filesystem paths in frontend code.

Core routes for the current React UI:

```text
GET  /api/state
GET  /api/sessions
POST /api/sessions
GET  /api/sessions/{id}/messages
GET  /api/sessions/{id}/events
POST /api/chat
```

Personal companion routes:

```text
GET  /api/journals
GET  /api/journal?date=YYYY-MM-DD
POST /api/journal
POST /api/journal/append
POST /api/journal/capture-session
GET  /api/memories?include_candidates=true
POST /api/memories/confirm
POST /api/reviews/weekly
```

Presence routes:

```text
GET  /api/schedules
POST /api/schedules
POST /api/schedules/toggle
POST /api/schedules/delete
POST /api/daemon/tick
```

## Production Mode

The frontend build should produce:

```text
frontend/dist/index.html
```

The FastAPI backend can serve static frontend output from:

```text
frontend/dist
frontend/build
web/dist
web/build
public
```

For the final Electron app, there are two viable production shapes:

1. Electron starts the bundled FastAPI backend, then loads a local URL served by FastAPI.
2. Electron loads local frontend files and frontend calls the bundled backend on `127.0.0.1:{port}`.

The preferred first packaging path is option 1 because FastAPI already owns static hosting and API routing.

## Packaging Contract

Python backend:

```text
PyInstaller bundles `python app.py` and the `kairos` package.
```

Electron app:

```text
electron-builder includes the PyInstaller backend artifact as an app resource.
```

Startup sequence:

1. Electron finds an available local port, defaulting to `8765`.
2. Electron starts the bundled backend process with `--host 127.0.0.1 --port {port}`.
3. Electron waits for `GET /api/health`.
4. Electron loads `http://127.0.0.1:{port}`.
5. On app exit, Electron stops the backend process.

## Current Blockers

As of 2026-05-16, `E:\Code\Kairos-frontend` still needs frontend-side sync:

- add missing `frontend/src/styles.css`
- replace mock API service with real backend calls
- update stale tests that expect `frontend/styles.css` and `frontend/app.js`

Backend can continue implementing agent, memory, and presence stages while frontend catches up.
