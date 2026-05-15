# First Round MVP

## Goal

The first implementation round should prove Kairos can run as a local-first personal assistant runtime without relying on an LLM, a GUI, network access, or a long-running daemon.

The minimum product-shaped loop is:

```text
kairos bootstrap
  -> creates .kairos/
  -> installs a default nightly journal reminder

kairos reflect "..."
  -> writes a Markdown journal
  -> extracts memory candidates

kairos schedule-add ... --due-now
kairos daemon-tick
  -> processes one due presence event
  -> queues and delivers a local reminder

kairos doctor
  -> shows local workspace health and counts
```

## In Scope

- Local `.kairos/` workspace initialization.
- Deterministic agent/tool loop scaffolding.
- Markdown daily journal writing.
- Memory candidate extraction.
- Schedule storage.
- Single-step daemon tick.
- CLI channel delivery.
- Smoke tests and deterministic unit tests.

## Out of Scope

- Real LLM integration.
- Real Windows toast integration.
- A long-running daemon process.
- Network search, weather, location, or MCP.
- Full desktop UI.
- Automatic promotion of memory candidates into confirmed memory.

## Acceptance

The first round is complete when these commands work on a temporary root:

```text
PYTHONPATH=src python -m kairos.cli bootstrap --root <tmp>
PYTHONPATH=src python -m kairos.cli reflect "我喜欢先讨论架构，今天很有能量" --root <tmp>
PYTHONPATH=src python -m kairos.cli schedule-add demo "Demo Reminder" --due-now --message "要写日记吗？" --root <tmp>
PYTHONPATH=src python -m kairos.cli daemon-tick --root <tmp>
PYTHONPATH=src python -m kairos.cli doctor --root <tmp>
```

And the repository passes:

```text
python scripts/smoke_check.py
python -m pytest
```
