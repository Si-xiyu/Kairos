# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start Commands

```bash
# Setup
python -m pip install -e .

# Initialize workspace and defaults
kairos bootstrap --root .

# Run development backend
python app.py --root . --host 127.0.0.1 --port 8765

# Development verification commands
python -m kairos.cli status                         # Workspace status
python -m kairos.cli doctor                        # Detailed diagnostics
python -m kairos.cli tools                       # List registered tools
python -m kairos.cli chat-once "/tool file.list path=."  # Single agent turn

# CLI workflow examples
python -m kairos.cli reflect "I like discussing architecture first" --no-candidates
python -m kairos.cli journal-create
python -m kairos.cli journal-append "今天发生了什么" "今天修复了一个 bug"
python -m kairos.cli schedule-add nightly-journal "Nightly Journal" --due-now --message "要写日记吗?"

# Tests
pytest tests/                                  # All tests
pytest tests/test_fastapi_app.py::test_health  # Single test
PYTHONPATH=src python -m pytest             # Via module
```

## Architecture Overview

Kairos is a local-first personal AI assistant runtime combining:
- **Coding agent capabilities** via tool-augmented agent loops
- **Long-term memory** with candidate review workflow
- **Lifelong journaling** with weekly review generation
- **Presence engine** with heartbeat and cron-driven proactive reminders
- **Permission-gated tool execution** with audit logging

### Module Structure

```
src/kairos/
├── core/           # Agent loop, session store, context, prompt builder
├── tools/          # Tool registry and router
├── permissions/    # Autonomy levels, audit logging
├── memory/        # Long-term memory storage
├── lifelog/       # Journal, reflection, weekly review
├── presence/      # Heartbeat, cron scheduler, daemon
├── channels/      # CLI and notification channels
├── delivery/      # Reliable message queue with retry
├── backend/       # FastAPI HTTP interface
└── cli.py         # CLI entry point
```

### Data Layout (`.kairos/`)

```
.kairos/
├── config.toml
├── conversations/         # JSONL session logs
├── journal/YYYY/MM/      # Daily Markdown journals
├── memory/
│   ├── user/, feedback/, project/, reference/   # Confirmed
│   └── candidates/                          # Unconfirmed
├── schedules/cron.json  # Scheduled jobs
├── delivery/
│   ├── pending/     # Queued messages
│   └── failed/      # Failed deliveries
└── audit/tool-calls.jsonl
```

### Tool Execution Flow

All tools use unified routing:

```
InboundMessage → AgentLoop.run_turn() → ToolRouter.call() → PermissionManager.check() → ToolHandler
                                                                      ↓
                                                              AuditLogger.record()
```

Tools have risk levels (low/medium/high/critical) and must pass permission checks before execution.

### API-First Backend

The backend exposes REST endpoints for frontend integration:

- `/api/state` - Full application snapshot for UI initialization
- `/api/sessions`, `/api/sessions/{id}/messages` - Conversation history
- `/api/journal`, `/api/journal/append` - Daily journal CRUD
- `/api/reflect` - Turn fragments into journal + memory candidates
- `/api/memories` - Confirm/reject candidate memories
- `/api/schedules` - Presence cron jobs
- `/api/daemon/tick` - Manual scheduler tick
- `/api/chat` - Single agent turn

Backend serves both API responses and static frontend builds.

### Memory System

Memories have types: `user`, `feedback`, `project`, `reference`, `life_pattern`, `energy_pattern`, `reflection_theme`.

Two workflows:
1. **Direct save**: `kairos memory-save <name> <description> <content>`
2. **Candidate flow**: `/api/reflect` extracts candidates → review → `/api/memories/confirm`

### Lifelog

Daily journals under `.kairos/journal/YYYY/MM/YYYY-MM-DD.md` with sections:
- 今天发生了什么
- 我在想什么
- 做了哪些事情
- 情绪与能量
- 有价值的对话
- Kairos 的观察
- 明天可以推进的事

Weekly review generates from recent daily journals via `/api/reviews/weekly`.

### Current Limitations

The agent loop scaffold is in place but LLM integration is not yet wired. Current behavior:
- `/tool` commands route through tool registry correctly
- Plain text input returns a prompt preview, not an LLM response
- MCP client and external tools are discovery-only in this round