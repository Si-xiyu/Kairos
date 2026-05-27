# Kairos Frontend

React + TypeScript + Vite prototype for the Kairos local-first Agent console.
The visual direction is a restrained AI desktop console: Claude/ChatGPT-like
conversation ergonomics, with an electronic magazine / e-ink palette from the
root `SKILL.md` as the surface treatment.

## Run

```powershell
cd E:\Code\Kairos\frontend
npm install
npm run dev
```

PowerShell may block `npm.ps1` on some Windows machines. Use `npm.cmd install` and `npm.cmd run dev` if that happens.
If the global npm cache is not writable, use `npm.cmd install --cache .\.npm-cache`.

## Current Scope

- REST-backed sessions, messages, chat turns, and Agent Inspector events.
- Desktop-style three-pane Agent console: sessions, message stream, inspector.
- Local UI state for sending, stopping, session selection, event folding, and search.
- Backend status ribbon with the active API base URL.

## API Boundary

The API boundary is isolated in `src/services/agentApi.ts`.

By default it calls:

```text
http://127.0.0.1:8765
```

Override with:

```powershell
$env:VITE_KAIROS_API_BASE = "http://127.0.0.1:8765"
```

Implemented calls:

- `GET /api/sessions` for conversation summaries.
- `POST /api/sessions` for new session records.
- `GET /api/sessions/{id}/messages` for persisted message history.
- `GET /api/sessions/{id}/events` for inspector events.
- `POST /api/chat` for local agent turns.

Future WebSocket work should keep the UI state shape in `src/types.ts` stable where possible. The Agent Inspector expects normalized `AgentEvent` records rather than raw log lines.
