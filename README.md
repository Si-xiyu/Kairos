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
```

For direct module execution before installing the package, set `PYTHONPATH=src`.
