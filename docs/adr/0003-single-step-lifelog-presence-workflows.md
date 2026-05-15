# 0003: Single-Step Life Log and Presence Workflows

## Status

Accepted

## Context

Kairos has separate foundations for:

- Markdown journals,
- reflection drafts,
- memory candidates,
- schedules,
- daemon ticks,
- delivery queues,
- and CLI channels.

Before implementing a real long-running daemon or LLM integration, the project needs product-shaped workflows that can run in tests and from the CLI without external services.

## Decision

Add deterministic single-step CLI workflows:

- `kairos reflect TEXT`
  - Builds a `DailyReflectionDraft` from a text fragment.
  - Writes draft sections into the daily journal.
  - Extracts and saves memory candidates under `.kairos/memory/candidates/`.

- `kairos schedule-add ...`
  - Adds a lightweight `ScheduledJob` to `.kairos/schedules/cron.json`.
  - Supports `at` and `every` schedules.
  - Can mark a job as due immediately with `--due-now`.

- `kairos daemon-tick`
  - Runs one synchronous scheduler/delivery tick.
  - Converts due presence events into outbound messages.
  - Enqueues and delivers through the existing delivery queue and channel manager.

These commands are not a replacement for the future daemon. They are stable wiring points for testing the runtime.

## Consequences

- Kairos can now demonstrate the core daily reflection loop without an LLM.
- Presence behavior can be exercised without a long-running background process.
- Future daemon and model integration can reuse the same stores and command paths.
