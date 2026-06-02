# Kairos

Kairos is a local-first personal AI assistant runtime.

It is designed to combine:

- coding-agent capabilities,
- personal memory,
- Markdown-based life logs,
- heartbeat / cron driven presence,
- channel-based delivery,
- and a strict permission layer.

Read [TECHNICAL_REQUIREMENTS.md](TECHNICAL_REQUIREMENTS.md) before implementing any module.

## Current Skeleton

This repository currently contains the shared runtime contracts and directory layout for parallel implementation.

```text
backend/
  app.py          backend application entrypoint
  src/kairos/
    core/         agent loop contracts
    tools/        tool registry and routing
    permissions/  autonomy and risk decisions
    memory/       personal memory storage
    lifelog/      journal and review generation
    presence/     heartbeat and cron
    channels/     CLI / notification channels
    delivery/     reliable outbound queue
frontend/
  src/            React/Vite UI
```

## Smoke Check

```text
python scripts/smoke_check.py
python app.py --root . --host 127.0.0.1 --port 8765
PYTHONPATH=backend/src python -m kairos.cli bootstrap
PYTHONPATH=backend/src python -m kairos.cli doctor
PYTHONPATH=backend/src python -m kairos.cli tools
PYTHONPATH=backend/src python -m kairos.cli run-tool file.list --arg path=.
PYTHONPATH=backend/src python -m kairos.cli chat-once "/tool file.list path=."
PYTHONPATH=backend/src python -m kairos.cli chat-once "你好，Kairos"
PYTHONPATH=backend/src python -m kairos.cli chat
PYTHONPATH=backend/src python -m kairos.cli reflect "我喜欢先讨论架构，今天很有能量"
PYTHONPATH=backend/src python -m kairos.cli schedule-add journal "Journal Check" --due-now --message "要写日记吗？"
PYTHONPATH=backend/src python -m kairos.cli daemon-tick
```

For direct module execution before installing the package, set `PYTHONPATH=backend/src`.

## Backend App

Run the backend with one command:

```text
python app.py
```

Default URL:

```text
http://127.0.0.1:8765
```

The app entrypoint runs FastAPI through Uvicorn. The lower-level service logic stays in `KairosBackend`, so tests can exercise the agent runtime without depending on HTTP transport details.

`app.py` at the repository root is a compatibility wrapper. The backend-owned entrypoint lives at `backend/app.py`, so `python backend/app.py --root .` also works from the repository root.

Frontend agents should use [docs/api/BACKEND_API.md](docs/api/BACKEND_API.md).

The frontend should usually start from `GET /api/state`, then call the narrower journal, memory, schedule, and capability endpoints as needed. The same app entrypoint can serve a built frontend from `frontend/dist`, `frontend/build`, `web/dist`, `web/build`, or `public`.

Reference mechanisms absorbed from OpenClaw and the Claude Code teaching repository are tracked in [docs/architecture/REFERENCE_REUSE_PLAN.md](docs/architecture/REFERENCE_REUSE_PLAN.md).

The FastAPI + Vite + Electron launch contract is tracked in [docs/development/APP_LAUNCH_CONTRACT.md](docs/development/APP_LAUNCH_CONTRACT.md).

## Commander Contracts

The current commander-owned runtime contracts include:

- append-only JSONL sessions via `SessionStore`,
- native tool registration via `build_native_registry`,
- permission-gated tool execution via `ToolRouter`,
- JSONL audit logs via `AuditLogger`,
- project-root constrained file tools.
- `AgentLoop` turns via `chat-once`, `chat`, and `POST /api/chat`.

## Model Provider MVP

Kairos defaults to a local fallback provider so the agent loop can run without secrets or network access.

To connect a real OpenAI-compatible chat API, use environment variables:

```powershell
$env:KAIROS_LLM_PROVIDER="openai-compatible"
$env:KAIROS_LLM_BASE_URL="https://api.openai.com/v1"
$env:KAIROS_LLM_API_KEY="..."
$env:KAIROS_LLM_MODEL="..."
python app.py --host 127.0.0.1 --port 8765 --root .
```

You can also use a repository-local `.env` file:

```text
KAIROS_LLM_PROVIDER=openai-compatible
KAIROS_LLM_BASE_URL=https://api.openai.com/v1
KAIROS_LLM_API_KEY=...
KAIROS_LLM_MODEL=gpt-4.1-mini
KAIROS_LLM_TIMEOUT=60
```

Or a JSON file at `.kairos/llm.json`, `kairos.llm.json`, or `llm.json`:

```json
{
  "provider": "openai-compatible",
  "base_url": "https://api.openai.com/v1",
  "api_key": "...",
  "model": "gpt-4.1-mini",
  "timeout": 60
}
```

Precedence is: process environment, `.env`, JSON config, then built-in defaults.

The loop now supports plain conversation, OpenAI-compatible model tool calls, and slash-command tools through the existing permission-gated path. Streaming comes next.

Context handling has an MVP three-layer strategy:

- large tool results are represented to the model as placeholders while the full result stays in the session log,
- old context can be summarized through the configured model provider,
- durable user facts/preferences and compression summaries are saved as memory candidates for later review.
