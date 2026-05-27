# Kairos Iteration Stages

This roadmap splits the next product rounds into commit-sized stages. Each completed stage should be tested and committed before moving on, so parallel agents can sync at precise version boundaries.

## Target Product Build Path

The agreed implementation path is:

1. **FastAPI backend** for Kairos agent logic and local data APIs.
2. **React + Vite frontend** connected to the backend and running in a browser.
3. **Electron shell** that loads the Vite dev server during development.
4. **Packaging** with PyInstaller for Python and electron-builder for the whole app.
5. **Release** as a Windows `.exe` installer.

The current stdlib HTTP backend remains useful as a contract prototype, but it should not become the long-term web framework. The next backend architecture stage is to migrate the existing API surface to FastAPI while preserving route compatibility.

## Round 1: Application Backend Surface

Goal: make `python app.py` a stable backend surface for the frontend.

Status: complete through R1-S4. R1-S5 is the framework alignment stage created after the FastAPI/Electron packaging direction was clarified.

Stages:

1. **R1-S1 State and CRUD API**
   - `/api/state`
   - journal list/read/save/append
   - memory create/confirm/update/delete
   - schedule list/create/toggle/delete
   - weekly review draft

2. **R1-S2 Frontend Adapter API**
   - `/api/sessions`
   - `/api/sessions/{id}/messages`
   - `/api/sessions/{id}/events`
   - normalize existing JSONL sessions into frontend-friendly records

3. **R1-S3 Static App Hosting**
   - serve built frontend from common output folders
   - return backend status at `/` when no frontend build exists
   - document launch flow for frontend agents

4. **R1-S4 Frontend Compatibility Check**
   - inspect `E:\Code\Kairos-frontend`
   - compare expected routes with backend routes
   - write handoff notes before waiting for frontend sync

5. **R1-S5 FastAPI Backend Migration**
   - add FastAPI and Uvicorn dependencies
   - expose the current backend service through FastAPI routes
   - keep `python app.py` as the single backend entrypoint
   - preserve stdlib service tests or replace them with FastAPI TestClient coverage
   - keep static frontend hosting behavior for Electron/prod builds

6. **R1-S6 React/Vite Dev Proxy Contract**
   - define backend base URL for the frontend
   - document Vite dev server and Electron `loadURL`
   - ensure CORS remains development-friendly
   - avoid hard-coding production paths in frontend API calls

## Round 2: Personal Memory and Lifelog Loop

Goal: make Kairos useful as a personal companion, not only a coding shell.

Stages:

1. **R2-S1 Journal Conversation Capture**
   - persist daily user/Kairos chat fragments into Markdown
   - append rather than overwrite by default
   - expose source metadata for frontend display
   - status: complete as `3ac8c21`

2. **R2-S2 Memory Review Workflow**
   - classify memory candidates more explicitly
   - expose candidate reasons and source journal links
   - require confirmation before long-term promotion

3. **R2-S3 Weekly Reflection Drafts**
   - summarize daily journals into weekly sections
   - include energy sources, drains, repeated themes, and next adjustments
   - keep output editable Markdown

4. **R2-S4 Guided Journaling Flow**
   - add structured prompts for multi-turn daily reflection
   - produce a journal outline or draft from answers
   - separate "raw conversation" from "edited diary"

## Round 3: Presence and Windows Companion Behavior

Goal: make Kairos feel present without becoming noisy.

Stages:

1. **R3-S1 Long-Running Daemon**
   - replace manual tick-only workflow with a loop
   - keep user interaction higher priority than background work
   - add start/stop/status endpoints or commands

2. **R3-S2 Notification Channel**
   - add Windows notification delivery
   - keep CLI delivery as test fallback
   - record notification delivery outcomes

3. **R3-S3 Presence Policy**
   - active hours
   - daily notification budget
   - cooldown after ignored notifications
   - skip reminders when today's journal already exists

4. **R3-S4 User Response Loop**
   - capture clicked/dismissed/snoozed notification outcomes
   - feed outcomes back into memory and scheduling policy

## Round 4: Real AI, Tools, Search, and MCP

Goal: upgrade deterministic scaffolding into a real agent loop.

Stages:

1. **R4-S1 LLM Provider Boundary**
   - provider abstraction
   - model config
   - non-streaming chat first
   - model tool-call round trip through the permission router
   - three-layer context compression MVP
   - status: MVP in progress on `dev/agent-loop-mvp`

2. **R4-S2 Streaming Chat and Events**
   - stream assistant deltas
   - normalize tool calls/results/runtime events
   - expose transport suitable for frontend inspector

3. **R4-S3 Tool Expansion**
   - weather
   - location
   - web search
   - shell/background task tools

4. **R4-S4 MCP Plugin Runtime**
   - connect discovered MCP manifests
   - prefix external tools as `mcp__{server}__{tool}`
   - route external tools through the same permission layer

5. **R4-S5 Prompt Assembly**
   - inject confirmed memories
   - inject skill manifests
   - load skill bodies on demand
   - support companion mode and coding mode

## Round 5: Productized Desktop App

Goal: turn Kairos into a single ordinary Windows application.

Stages:

1. **R5-S1 Process Packaging**
   - PyInstaller bundle for the Python/FastAPI backend
   - single launcher contract between Electron and bundled backend
   - clean logs and crash reports

2. **R5-S2 Tray and Startup**
   - system tray status
   - open main window
   - optional startup on login

3. **R5-S3 Settings and Secrets**
   - model provider settings
   - API keys
   - location/weather preferences
   - notification permissions

4. **R5-S4 Backup and Data Portability**
   - export/import `.kairos`
   - local data directory selection
   - clear memory/journal controls

5. **R5-S5 Installer Release**
   - electron-builder configuration
   - bundled backend artifact included in Electron resources
   - Windows `.exe` installer
   - first-run bootstrap flow

## Frontend Checkpoint

Observed `E:\Code\Kairos-frontend` state on 2026-05-16:

- branch: `frontend`
- dirty/untracked frontend implementation exists
- current UI is React + TypeScript + Vite
- `src/services/agentApi.ts` still returns mock data
- handoff expects session/message/event APIs
- current frontend tests appear to describe an older static HTML/CSS/JS implementation, while the actual frontend is Vite

Backend implication:

- implement R1-S2 before asking frontend to sync
- do not require frontend to use `/api/state` only; also support session-oriented routes that fit the current UI shape
