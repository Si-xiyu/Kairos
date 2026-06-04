# Kairos Context

## Personal Operating Console

Kairos is a local-first console for the user's work and life, with conversation, memory, life logs, reminders, and approved tools gathered into one long-running personal workspace.
_Avoid_: Treating Kairos primarily as a coding assistant.

## Personal Assistant

Kairos is a local-first assistant that can hold conversations with the user, remember useful preferences, run approved tools, and proactively surface reminders.

## Coding Mode

Coding mode is a focused Kairos mode for local project and file work. It is a high-capability mode inside the personal operating console, not the product's primary identity.
_Avoid_: General-purpose coding agent as the main product category.

## Personal Workspace

The personal workspace is the user's global Kairos home for personal memory, life logs, reminders, settings, and model configuration. A user has one primary personal workspace, while projects may be attached to it as narrower scopes.
_Avoid_: Treating every code project as a separate Kairos identity.

## Project Scope

A project scope is a local directory boundary where Kairos is allowed to work with fewer interruptions. Outside an attached project scope, local file work should be blocked or require explicit user approval.
_Avoid_: Treating a project scope as a Claude Code-style coding workspace or letting it implicitly access all personal data.

## App View

An app view is a first-class Kairos surface for a durable part of the user's life or work, such as Today, chat, journals, todos, project scopes, or settings. Information created in conversation must remain reachable through the relevant app view or settings surface.
_Avoid_: Chat-only access to durable user data.

## Today View

The Today view is Kairos's home surface: a daily operating panel for reminders, journal state, memory review, recent sessions, and background status. It is paired with a chat sidebar so the user can act conversationally without making chat the whole app.
_Avoid_: A chat-only home screen.

## Desktop App

The desktop app is the primary Kairos product form: a local Windows application with a ChatGPT-like desktop feel, persistent navigation, Today as the home surface, and a contextual chat sidebar. The desktop app should feel like a usable personal console, not a developer-only backend demo.
_Avoid_: Treating the browser UI or CLI as the final user experience.

## Contextual Chat

Contextual chat is the chat sidebar behavior where Kairos answers and acts in relation to the current app view. A global assistant conversation still exists, but view-specific chat should understand the active journal, memory item, schedule, project, or Today panel.
_Avoid_: One undifferentiated chat context for the whole app.

## Approved Action

An approved action is a Kairos action that has passed the user's autonomy and permission boundary. Low-risk actions may run automatically, while high-risk actions require explicit user confirmation before changing files, long-term facts, schedules, notifications, or external systems.
_Avoid_: Silent high-risk automation.

## Scope Permission

Scope permission is the user's grant for Kairos to work inside an attached project scope. Reads and low-risk writes may proceed with fewer interruptions inside the scope, while overwrites, bulk changes, deletion, command execution, and all out-of-scope file work still require explicit approval.
_Avoid_: Treating a scoped directory as unrestricted access.

## Memory

Memory is Kairos's agent-facing context store for preferences, routines, follow-ups, and other facts that help the assistant behave consistently. Memory supports model context and behavior, while the user's durable knowledge base belongs in journals.
_Avoid_: Treating memory as the user's primary knowledge base.

## Memory Inbox

The memory inbox is the review boundary for proposed agent context before it becomes long-term memory. Candidate memories must stay there until they are confirmed, edited, merged, or rejected through an approval surface.
_Avoid_: Automatically promoting candidate memories into confirmed memory.

## Knowledge Base

The knowledge base is the user's durable, readable archive of useful records, notes, reflections, and summaries. In Kairos, journals should carry this role because they are curated artifacts produced from conversations and events.
_Avoid_: Using hidden agent memory as the user's knowledge base.

## Diary

A diary is a dated Markdown journal artifact for daily reflection and life records. Diary files are one of the two built-in knowledge base categories, with attributes such as tags stored in YAML front matter.
_Avoid_: Mixing undated topic records into diary files by default.

## Record

A record is a non-diary Markdown journal artifact for curated notes, summaries, plans, decisions, or other reusable knowledge. Record attributes such as tags are stored in YAML front matter instead of product-level directory categories.
_Avoid_: Creating many product-level knowledge categories beyond diary and record.

## Journal

A journal is an editable archived record produced from high-value daily events, reflections, or conversations. Raw chat can be a source for a journal, but the journal itself should read like curated notes, a diary, or a review artifact.
_Avoid_: Treating journals as raw chat transcripts.

## Journal Capture

Journal capture is Kairos's low-risk action of saving a curated record into the journal or knowledge base after a valuable conversation or event. It does not require explicit pre-approval, but Kairos should clearly tell the user after the record has been added.
_Avoid_: Asking for confirmation before every journal archive or silently archiving without feedback.

## Todo

A todo is a reliable user commitment, task, or scheduled obligation that Kairos should track explicitly in a first-class todo view. Todos created from conversation require confirmation, can be created through approved tool calls, and remain editable or deletable by the user.
_Avoid_: Treating todos as casual heartbeat suggestions.

## Todo List

A todo list is a lightweight grouping for todos that helps both the user and Kairos understand where a commitment belongs. Lists should support human scanning while also giving Kairos stable structure for reminders, heartbeat analysis, context selection, and approved todo tool calls.
_Avoid_: Treating lists as visual-only folders or full project-management boards.

## Routine

A routine is a habit, preference, or recurring life pattern that may inform companion nudges but is not a reliable todo by itself. Routines belong in memory as a distinguishable kind of personal context, not in the todo list or a dedicated app view.
_Avoid_: Mixing habits and preferences into the reliable todo system.

## Follow-Up

A follow-up is a topic Kairos may revisit later because the user mentioned ongoing interest, uncertainty, or unfinished reflection. Follow-ups belong in memory as distinguishable revisit cues, and should not become todos unless the user confirms a concrete action or reminder.
_Avoid_: Treating every interesting conversation topic as a task.

## High-Level Reminder

A high-level reminder is a dependable notification for a confirmed todo, schedule, class, deadline, or other explicit commitment. It should be visible, timely, and harder to miss than companion nudges.
_Avoid_: Silent or best-effort handling of confirmed commitments.

## Companion Nudge

A companion nudge is a low-level reminder generated from preferences, habits, ongoing interests, or heartbeat analysis. It should be frequency-limited and easy to ignore, because it supports reflection rather than enforcing a commitment.
_Avoid_: Letting companion nudges feel like task alarms.

## Agent Loop

The agent loop is the turn-by-turn runtime that records user messages, asks a model or local fallback for a response, executes permitted tools, and stores the resulting session events.

## Tool

A tool is an action Kairos can call through the shared permission and audit pipeline.

## MCP Tool

An MCP tool is a tool exposed by a configured external MCP server and made available to Kairos through the same permission and audit pipeline as native tools.

## Heartbeat

Heartbeat is Kairos's proactive check for whether it should stay silent or create a reminder. If no action is needed, the canonical result is `HEARTBEAT_OK`.

## Delivery Queue

The delivery queue is the durable local queue for outbound messages and notifications, including retry and failed-delivery tracking.

## Windows Notification

A Windows notification is a local desktop notification used by Kairos to surface a reminder without requiring the main chat window to be open.
