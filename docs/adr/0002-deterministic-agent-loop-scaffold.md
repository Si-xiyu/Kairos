# 0002: Deterministic Agent Loop Scaffold

## Status

Accepted

## Context

Kairos will eventually call an LLM, but the repository needs a stable integration path before model integration:

```text
InboundMessage -> SessionStore -> AgentLoop -> ToolRouter -> AuditLogger -> OutboundMessage
```

This path must be testable without network access or API keys.

## Decision

Add a deterministic `AgentLoop` scaffold with:

- `RuntimeContext` for paths, sessions, tools, permissions, and audit logging.
- `PromptBuilder` / `PromptBundle` for future model input assembly.
- `parse_agent_command()` for local `/tool ...` commands.
- `kairos chat-once` as a CLI smoke path.

The scaffold does not pretend to be an LLM. Normal text returns a runtime-ready prompt preview. Tool commands execute through the same permission-gated router that future model tool calls will use.

## Consequences

- Model integration can be added behind the existing `AgentLoop` shape.
- CLI and tests can exercise the core execution path without external services.
- Workers can keep building Memory/LifeLog and Presence/Delivery without needing a model provider.
