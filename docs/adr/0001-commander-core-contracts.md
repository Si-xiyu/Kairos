# 0001: Commander Core Contracts

## Status

Accepted

## Context

Kairos is being implemented in parallel worktrees. The first shared risk is that each worker may invent incompatible message, path, tool, or permission types.

## Decision

The commander worktree owns the first shared runtime contracts:

- `KairosPaths` for local workspace paths.
- `InboundMessage` and `OutboundMessage` for channel-neutral messaging.
- `SessionStore` and `SessionEvent` for append-only JSONL conversations.
- `ToolRegistry`, `ToolSpec`, and `ToolResult` for tool declaration.
- `ToolRouter` for permission-gated execution.
- `PermissionManager` and `AutonomyLevel` for allow / ask / deny decisions.
- `AuditLogger` and `AuditEvent` for JSONL audit trails.

Workers should use these contracts instead of creating parallel equivalents.

## Consequences

- Memory, Life Log, Presence, Channel, and Delivery modules can evolve independently while sharing the same runtime vocabulary.
- High-risk work remains gated through the permission layer.
- Future LLM integration can call the same `ToolRouter` that CLI smoke tests use.
