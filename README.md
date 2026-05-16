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
src/kairos/
  core/          agent loop contracts
  tools/         tool registry and routing
  permissions/   autonomy and risk decisions
  memory/        personal memory storage
  lifelog/       journal and review generation
  presence/      heartbeat and cron
  channels/      CLI / notification channels
  delivery/      reliable outbound queue
```

## Smoke Check

```text
python scripts/smoke_check.py
python app.py --root . --host 127.0.0.1 --port 8765
PYTHONPATH=src python -m kairos.cli bootstrap
PYTHONPATH=src python -m kairos.cli doctor
PYTHONPATH=src python -m kairos.cli tools
PYTHONPATH=src python -m kairos.cli run-tool file.list --arg path=.
PYTHONPATH=src python -m kairos.cli chat-once "/tool file.list path=."
PYTHONPATH=src python -m kairos.cli reflect "我喜欢先讨论架构，今天很有能量"
PYTHONPATH=src python -m kairos.cli schedule-add journal "Journal Check" --due-now --message "要写日记吗？"
PYTHONPATH=src python -m kairos.cli daemon-tick
```

For direct module execution before installing the package, set `PYTHONPATH=src`.

## Backend App

Run the backend with one command:

```text
python app.py
```

Default URL:

```text
http://127.0.0.1:8765
```

Frontend agents should use [docs/api/BACKEND_API.md](docs/api/BACKEND_API.md).

## Commander Contracts

The current commander-owned runtime contracts include:

- append-only JSONL sessions via `SessionStore`,
- native tool registration via `build_native_registry`,
- permission-gated tool execution via `ToolRouter`,
- JSONL audit logs via `AuditLogger`,
- project-root constrained file tools.
- deterministic `AgentLoop` turns via `chat-once`.
