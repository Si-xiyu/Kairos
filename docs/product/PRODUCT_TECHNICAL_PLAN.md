# Kairos Product and Technical Plan

Kairos is a local-first personal operating console. It should become a usable Windows desktop app with a ChatGPT-like desktop feel, while keeping Today, Todo, Journal, Project Scopes, and Settings as first-class product surfaces. Chat remains always available as a contextual sidebar, but it is not the whole product.

## Product Position

Kairos is for personal work and life continuity:

- reliable todos and reminders,
- curated diaries and records,
- evidence-based retrieval over authorized knowledge,
- local project scopes where Kairos can work with files,
- agent memory used as internal context,
- low-frequency companion nudges,
- and approved local tools.

Coding agent behavior is a strong mode inside a project scope. It exists to operate local files and project tasks, not to define the whole product.

## Target Desktop Experience

The expected end-user result is similar in quality and immediacy to a ChatGPT desktop app:

- desktop launcher, not a developer-only web page,
- persistent left navigation,
- central app surface,
- contextual chat sidebar,
- visible connection/model/status affordances,
- fast local startup,
- readable history and artifacts,
- and ordinary app settings for storage, model, notifications, and permissions.

The first production shape should be Electron loading the local React app and managing the FastAPI backend process. The browser UI remains useful for development, but the user-facing target is the desktop shell.

## Primary Navigation

First-level app surfaces:

- **Today**: home surface with today's todos, reminders, diary state, recent records, recent sessions, pending approvals, and background status.
- **Chat**: can expand into a full view, but normally appears as a contextual sidebar.
- **Todo**: a compact reliable todo system comparable to iOS Reminders basics.
- **Journal**: the user's readable knowledge base, split into diary and record artifacts.
- **Project Scopes**: local directory authorization boundaries where Kairos can work with fewer interruptions.
- **Settings**: model provider, storage paths, notification settings, memory management, permissions, MCP/search/weather configuration.

## Core Domain Boundaries

### Todo

Todo is for explicit commitments:

- `event`: fixed-time class, meeting, appointment, deadline.
- `task`: something the user intends to complete.
- `reminder`: a simple reminder without a larger task model.

Todos can be created manually or through an approved Kairos tool call. Natural language extraction should show a confirmation card before creating a reliable todo. Users can edit and delete todos directly from the Todo view.

Todo lists are lightweight groupings. They are for both human scanning and Kairos reasoning; they should help reminders, heartbeat analysis, context selection, and todo tool calls. They are not full project-management boards.

### Journal

Journal is the user-facing knowledge base. It uses Markdown files as the durable source of truth and has two built-in categories:

- `diary`: dated daily reflection and life records.
- `record`: non-diary notes, summaries, plans, decisions, learning notes, and other reusable knowledge.

All diary and record files are `.md` files. Metadata is stored in YAML front matter, with `tags` as the only built-in classification mechanism. The storage location is configurable in Settings.

Journal capture is low risk. Kairos may add curated diary or record entries after a valuable conversation without pre-approval, but it must tell the user afterward and offer obvious correction paths such as edit, move, or undo.

### RAG and Knowledge Retrieval

RAG is Kairos's local evidence retrieval layer over authorized user knowledge. It is not a standalone paper QA system and does not replace the Agent Loop, Journal, Memory, Project Scope, or permission model.

The first version should use:

- SQLite FTS5 for BM25 keyword search.
- Optional Ollama embeddings for semantic search.
- RRF to merge BM25 and vector rankings.
- Automatic BM25 fallback when embedding is unavailable.
- Citation-first answers over retrieved evidence.

RAG sources are explicit:

- `journal`: built-in Diary and Record artifacts.
- `uploads`: user-uploaded `.txt`, `.md`, and `.pdf` files.
- `project:{scope_id}`: files inside an enabled and authorized Project Scope.

The first version must not support broad scopes such as `all`, `*`, `filesystem`, `memory`, or `chat`. Raw Chat should become Diary or Record artifacts before entering the searchable knowledge base. Memory remains agent-facing context, not a user-facing RAG source.

RAG exposes both HTTP and tool adapters:

```text
RetrievalService
  -> POST /api/rag/search
  -> POST /api/rag/answer
  -> rag.search tool
  -> rag.answer tool
```

The HTTP API is for frontend search, "ask from records" flows, and debugging. The tool adapter is for Kairos agent turns and must pass through `ToolRouter`, `PermissionManager`, and `AuditLogger`.

`rag.search` returns evidence chunks and citations. `rag.answer` uses the currently configured chat provider to synthesize an answer from citations. If no sufficient evidence exists, it must say so instead of fabricating.

The detailed implementation plan is tracked in [../architecture/RAG_IMPLEMENTATION_PLAN.md](../architecture/RAG_IMPLEMENTATION_PLAN.md).

### Memory

Memory is agent-facing context, not the user's primary knowledge base. It stores preferences, routines, follow-ups, and facts that help Kairos behave consistently. Memory should support review and correction in Settings, but it does not need a first-level app view.

Routines and follow-ups belong in memory as distinguishable context:

- A routine is a habit, preference, or life pattern that may inform companion nudges.
- A follow-up is a topic Kairos may revisit later.

Neither should enter Todo unless the user confirms a concrete task, event, or reminder.

### Companion Nudges

Companion nudges are low-level reminders based on routines, follow-ups, memory, and heartbeat analysis. They are not reliable task alarms. They must be frequency-limited, easy to ignore, and sensitive to quiet hours and user feedback.

### Project Scopes

A project scope is a local directory boundary where Kairos is allowed to work with fewer interruptions. It is not a Claude Code-style workspace UI.

Recommended permission behavior:

- scope reads: usually allowed,
- low-risk writes: allowed or lightly confirmed depending on autonomy settings,
- overwrites, deletion, bulk edits, shell commands: require confirmation,
- out-of-scope file access: blocked or explicitly approved.

## Permission Model

All meaningful actions should use the same approved-action pipeline:

```text
Kairos action -> tool call -> permission decision -> audit -> execution -> user-visible result
```

Existing `ToolRouter`, `PermissionManager`, and `AuditLogger` should be kept and productized.

Default policy:

- Low-risk local organization and journal capture may run automatically.
- Reliable todos require confirmation before creation from conversation.
- High-level reminders require confirmed todos.
- File writes, destructive actions, shell commands, external network tools, and cross-scope access require stronger approval.
- Agent-triggered RAG searches over explicit scopes must use RAG tools through the permission and audit pipeline.
- User-triggered RAG API calls must validate requested scopes and record retrieval events.
- Every tool action should be explainable in the inspector or activity log.

## Technical Architecture

Keep the current foundation:

```text
Electron desktop shell
  -> React/Vite frontend
  -> FastAPI local backend
  -> Kairos runtime modules
  -> local stores and tool providers
```

Current working assets to preserve:

- FastAPI route surface.
- `KairosBackend` service layer.
- append-only JSONL sessions.
- permission-gated tool router.
- audit logs.
- memory and journal stores.
- retrieval service for Journal/Record, uploads, and authorized Project Scopes.
- schedule/delivery/heartbeat foundations.
- React session UI and agent inspector.
- OpenAI-compatible provider boundary.
- stdio MCP MVP.

Model/API direction:

- The near-term default API target is DeepSeek.
- Keep the provider implementation OpenAI-compatible instead of hard-coding one vendor into the agent loop.
- Settings should expose DeepSeek-oriented defaults while still allowing base URL, API key, and model overrides.
- RAG answer synthesis should use the currently configured chat provider.
- RAG embeddings should default to local Ollama (`http://127.0.0.1:11434`) with `bge-m3` or `nomic-embed-text`, and degrade to BM25 if unavailable.
- Other providers can remain possible later, but they are not the product baseline for the next build slice.

Storage responsibilities:

- Markdown: diary and record knowledge base.
- JSONL: sessions, audit, tool events, append-only runtime streams.
- SQLite: todos, settings, notification state, cross-artifact queries, and RAG index tables.
- `.kairos/search/index.sqlite`: RAG documents, chunks, FTS5 BM25 index, embeddings, and index jobs.
- `.kairos/search/events.jsonl`: lightweight local retrieval events.
- Vector storage: first-version local SQLite BLOB/JSON plus Python similarity; later optional `sqlite-vec` if needed.

## Implementation Stages

### Stage 0: Product Alignment and Quality Baseline

Goal: make the repo match the new product direction.

- Fix user-visible mojibake in code and docs.
- Update old docs that still describe Kairos primarily as a coding assistant.
- Add product terminology to `CONTEXT.md`.
- Keep tests green with workspace-local pytest temp settings.
- Document current backend/frontend launch flow.

### Stage 1: Desktop-Like App Shell

Goal: make the current frontend feel like the target app, even before Electron packaging.

- Replace chat-only layout with left navigation, Today main panel, and chat sidebar.
- Add app-level status bar for backend/model/daemon state.
- Preserve full chat session access.
- Keep agent inspector visible but secondary.
- Add responsive layout suitable for desktop window sizes.

### Stage 2: Todo MVP

Goal: deliver reliable reminders before companion behavior.

- Introduce todo data model and API.
- Support todo lists, event/task/reminder kinds, due time, reminder time, reminder level, completion state, source link.
- Add Todo view for create/edit/delete/complete.
- Add Kairos tool calls for proposed todo creation and updates.
- Add confirmation card before creating todos from conversation.
- Connect high-level reminders to the delivery/notification system.

### Stage 3: Journal Knowledge Base

Goal: make Journal the user's readable archive.

- Define Markdown + YAML front matter reader/writer.
- Support diary and record artifacts.
- Add Journal view with diary/record switch, search, tags, editor, and source links.
- Convert session capture into curated journal capture rather than raw transcript copy.
- Add post-capture user feedback: added, edit, undo, move between diary and record.
- Introduce RAG indexing for Diary and Record artifacts.
- Add `/api/rag/search` for `journal` scope.
- Register `rag.search` as a permission-gated native tool.

### Stage 4: Settings and Trust

Goal: make local-first trust visible.

- Add Settings view for model provider, storage paths, notification policy, project scopes, memory review, MCP/search/weather providers.
- Add RAG settings for embedding provider, embedding model, index location, and rebuild index.
- Add approval queue/activity log UI around tool calls.
- Make scope permissions configurable.
- Add quiet hours, notification budget, and low-level nudge frequency controls.
- Show retrieval fallback status when vector search is unavailable.

### Stage 5: Project Scopes and File Work

Goal: make local file work useful without becoming the whole app.

- Add Project Scopes view for attaching directories and editing permissions.
- Expand file tools around scoped access.
- Add explicit Project Scope indexing for `project:{scope_id}` RAG searches.
- Respect safe-text file rules and ignore/exclude patterns during project indexing.
- Add safer file write previews and diff display.
- Add approved shell/test tools only after permission UX is solid.

### Stage 6: Uploads and Evidence-Based Answers

Goal: let Kairos answer from authorized knowledge with citations.

- Add Uploads source for `.txt`, `.md`, and `.pdf` files.
- Track upload parsing/indexing states: uploaded, parsing, indexed, failed.
- Add `/api/rag/answer` and `rag.answer`.
- Require citations in RAG answers.
- Add answer UI that shows citations and retrieval status.
- Record local retrieval events for search and answer calls.

### Stage 7: Electron Desktop Release

Goal: package Kairos as an ordinary Windows desktop app.

- Electron starts/stops bundled FastAPI backend.
- Tray menu: open app, backend status, pause notifications, quit.
- Windows notification integration.
- Startup on login option.
- Logs and crash report location.
- Installer packaging.

## Immediate Next Build Slice

The next concrete build slice should be:

1. Add `backend/src/kairos/retrieval/` with SQLite index store, chunking, BM25 search, RRF merge, and retrieval events.
2. Index existing Diary and Record artifacts into `.kairos/search/index.sqlite`.
3. Implement `POST /api/rag/search` for `scope=["journal"]`.
4. Register `rag.search` as a native tool that requires explicit scopes.
5. Add Ollama embedding adapter with automatic BM25 fallback.
6. Add frontend Journal search UI that displays citations and retrieval status.

This adds RAG as Kairos's evidence retrieval layer while keeping the existing desktop app, Journal, Project Scope, and permission architecture intact.
