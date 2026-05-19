# Kairos Frontend

React + TypeScript + Vite prototype for the Kairos local-first Agent console.
The visual direction is a restrained AI desktop console: Claude/ChatGPT-like
conversation ergonomics, with an electronic magazine / e-ink palette from the
root `SKILL.md` as the surface treatment.

## Run

```powershell
npm install
npm run dev
```

PowerShell may block `npm.ps1` on some Windows machines. Use `npm.cmd install` and `npm.cmd run dev` if that happens.
If the global npm cache is not writable, use `npm.cmd install --cache .\.npm-cache`.

## Current Scope

- Static mock sessions, messages, and Agent Inspector events.
- Desktop-style three-pane Agent console: sessions, message stream, inspector.
- Local UI state for sending, stopping, session selection, event folding, and search.
- No backend calls are made yet.

## API / WebSocket Handoff

The API boundary is isolated in `src/services/agentApi.ts`. Replace the mock implementations there with:

- `GET /api/sessions` for conversation summaries.
- `GET /api/sessions/:id/messages` for persisted message history.
- `POST /api/chat` or a WebSocket `client_message` event for user input.
- WebSocket events for streaming assistant deltas, tool calls, tool results, runtime status, and memory events.

Keep the UI state shape in `src/types.ts` stable where possible. The Agent Inspector expects normalized `AgentEvent` records rather than raw log lines.
