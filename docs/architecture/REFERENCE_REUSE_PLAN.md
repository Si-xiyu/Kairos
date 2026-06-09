# Reference Reuse Plan

This note records what Kairos is deliberately reusing from:

- `E:\Code\openclaw`
- `E:\Code\learn-claude-code`

The goal is not to copy those repositories wholesale. Kairos should absorb the mechanisms that fit its product shape: a local-first personal companion that can also act as a coding agent.

## From OpenClaw / `claw0-main`

Reusable mechanisms:

- **Heartbeat lane**: background presence should check whether it is appropriate to speak, then yield when the user is actively interacting.
- **Cron jobs**: scheduled work is data-driven and persisted as JSON.
- **Failure budget**: repeated cron failures auto-disable a job instead of looping forever.
- **Reliable delivery**: messages are written to disk before delivery, then retried with backoff.
- **Companion identity files**: stable identity, memory, and heartbeat instructions are separate long-lived documents.

Already reflected in Kairos:

- `ScheduleStore` persists jobs as `.kairos/schedules/cron.json`.
- `DaemonRuntime.tick()` converts due schedules into outbound delivery.
- `DeliveryQueue` uses JSON files, atomic replace, retry state, and failed delivery storage.
- `KairosBackend.bootstrap()` installs a default nightly journal reminder.

Next integration steps:

- Add a real long-running daemon loop with a lane lock.
- Add Windows notification delivery as a first non-CLI channel.
- Add active-hours and notification-budget checks before proactive messages.
- Add companion identity/profile files under `.kairos/profile/`.

## From `learn-claude-code`

Reusable mechanisms:

- **Skill discovery before loading**: expose lightweight skill manifests, load full `SKILL.md` only when needed.
- **Memory boundary**: memory is for cross-session facts and preferences, not transient task state.
- **Permission pipeline**: tool intent must pass through deny/mode/allow/ask style checks before execution.
- **MCP/plugin layering**: external tools join the same router and permission surface as native tools.
- **Background tasks**: slow operations should return a task id and report completion through notifications.

Already reflected in Kairos:

- `SkillRegistry` discovers `skills/**/SKILL.md` and `.kairos/skills/**/SKILL.md`.
- `/api/capabilities` exposes native tools, skills, and discovered MCP/plugin manifests.
- `MemoryStore` keeps confirmed memories separate from candidates.
- Tool execution already flows through `ToolRouter` and `PermissionManager`.
- Backend state exposes delivery, schedules, memory, and capability counts for the frontend.

Next integration steps:

- Add true MCP client transports and prefix external tools as `mcp__{server}__{tool}`.
- Add background task records under `.kairos/tasks/runtime/`.
- Add permission modes beyond numeric autonomy levels: `plan`, `default`, and `auto`.
- Inject skill manifests and confirmed memory summaries into the eventual LLM prompt builder.

## First-Round Backend Contract

The first application round now treats the backend as a stable local app service:

- `/api/state` is the frontend's primary startup snapshot.
- Journals can be listed, read, saved, and appended.
- Memory candidates can be reviewed, confirmed, edited, and deleted.
- Schedules can be listed, created, toggled, deleted, and ticked.
- Capabilities expose tools, skills, and discovered plugin manifests.
- Static frontend output can be served from common build directories by the same `python app.py` entrypoint.

This gives the frontend a single application surface while preserving the deeper agent architecture for later rounds.
