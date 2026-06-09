# Kairos RAG Implementation Plan

Kairos RAG is the local retrieval and evidence-based answering layer for the user's authorized knowledge sources. It is not a standalone paper QA system and should not replace the Kairos Agent Loop, ToolRouter, PermissionManager, Journal, Memory, or Project Scope model.

The first version should be simple, local-first, inspectable, and resilient:

- SQLite FTS5 BM25 keyword search.
- Optional Ollama embedding search.
- RRF hybrid ranking.
- Automatic BM25 fallback when embedding is unavailable.
- Evidence-first answers with citations.
- No LangChain, no LangGraph, no PostgreSQL, no OpenSearch, no Redis, no Airflow.

## Goals

- Let users search and ask questions over their authorized Kairos knowledge.
- Let Kairos use the same retrieval capability through permission-gated tools.
- Make Journal/Record the default user-facing knowledge base.
- Support explicit uploads and explicitly authorized Project Scopes.
- Keep deployment suitable for a local desktop app.

## Non-Goals

- Do not build a general multi-user RAG service.
- Do not index all local files.
- Do not search Memory, raw Chat, Settings, Audit, or unrestricted filesystem content.
- Do not automatically write retrieved content into Memory.
- Do not introduce rerankers, semantic chunking, LangGraph workflows, or external search infrastructure in the first version.

## Architecture

RAG is a backend service with two adapters:

```text
RetrievalService
  - index_document(...)
  - search(...)
  - hybrid_search(...)
  - answer(...)

HTTP API adapter
  - POST /api/rag/search
  - POST /api/rag/answer

Tool adapter
  - rag.search
  - rag.answer
```

The API adapter is for the frontend, external local callers, and debugging panels. The tool adapter is for Kairos agent turns and must go through:

```text
Agent Loop -> ToolRouter -> PermissionManager -> AuditLogger -> RetrievalService
```

The tool adapter should call `RetrievalService` directly. It should not call the HTTP endpoint internally.

## Supported Scopes

Request scope shape:

```json
{
  "scopes": ["journal"]
}
```

Allowed first-version scopes:

- `journal`: built-in Diary and Record artifacts.
- `uploads`: files explicitly uploaded by the user into the knowledge area.
- `project:{scope_id}`: files inside an enabled and authorized Project Scope.

API calls may default to:

```json
{"scopes": ["journal"]}
```

Agent tools should require explicit `scopes` to avoid accidental broad retrieval.

Unsupported first-version scopes:

- `all`
- `*`
- `filesystem`
- `memory`
- `chat`

`project:{scope_id}` must match an enabled Project Scope and pass scope permission checks before indexing or search.

## Knowledge Sources

### Journal

Journal is the default RAG source and includes:

- Diary artifacts.
- Record artifacts.

Daily raw chat should not be searched directly. Useful conversations should first become Diary or Record artifacts through Journal Capture.

### Uploads

Uploads are user-provided knowledge files. Uploading a file is explicit authorization for that file to enter the `uploads` RAG scope.

First-version supported file types:

- `.txt`
- `.md`
- `.pdf`

Unsupported first-version types:

- `.doc`
- `.docx`
- PowerPoint files
- images
- OCR-only documents

PDF parsing should use a lightweight dependency such as `pypdf` first. Docling can be evaluated later if PDF/Word extraction quality becomes a product bottleneck.

Upload state should be visible:

- `uploaded`
- `parsing`
- `indexed`
- `failed`

Users must be able to delete an upload or disable indexing for it. One failed upload must not block other indexed content.

### Project Scopes

Project files can be indexed only when the user explicitly selects an enabled Project Scope.

Default project indexing includes safe text-like files only, such as:

- `.md`
- `.txt`
- `.rst`
- `.py`
- `.ts`
- `.tsx`
- `.js`
- `.json`
- `.yaml`
- `.yml`
- `.toml`

Default project indexing excludes:

- `.env`
- key/secret files
- `.git`
- `node_modules`
- `.venv`
- `dist`
- `build`
- binary files
- images/audio/video
- large lock files

PDF and Word files inside project directories should not be scanned by default. Put them in `uploads` if the user wants them indexed.

## Storage

Index file:

```text
.kairos/search/index.sqlite
```

Core tables:

```text
documents
chunks
chunks_fts
embeddings
index_jobs
```

Recommended responsibilities:

- `documents`: one indexed source document, such as a Diary, Record, upload file, or Project Scope file.
- `chunks`: chunk text plus source metadata.
- `chunks_fts`: SQLite FTS5 virtual table for BM25.
- `embeddings`: chunk vectors and embedding metadata.
- `index_jobs`: parsing, chunking, embedding, indexing, failure, and rebuild status.

Vector storage in the first version can use SQLite BLOB or JSON plus Python similarity calculation. If this becomes slow, migrate to `sqlite-vec` or another local vector extension later.

Do not use PostgreSQL, OpenSearch, Redis, or a standalone vector database for the first version.

## Chunking

First-version chunking should be deterministic and simple:

```text
target_chars = 800
overlap_chars = 120
min_chars = 80
max_chars = 1200-1500
```

Chunking rules:

- Markdown: prefer heading and paragraph boundaries.
- Plain text: prefer paragraph boundaries.
- Code: prefer function/class boundaries, then blank lines, then fixed-length fallback.
- PDF: parse into text/sections first, then treat as structured text.

Do not implement semantic chunking or complex AST chunking in the first version.

Each chunk should store:

- `heading`
- `line_start`
- `line_end`
- `page`
- `char_start`
- `char_end`
- `source_hash`

## Retrieval

Search pipeline:

```text
validate request
-> validate scopes and permissions
-> BM25 search through SQLite FTS5
-> vector search if embeddings are available
-> RRF merge
-> return top results with citations
```

RRF scoring:

```text
score = 1 / (k + bm25_rank) + 1 / (k + vector_rank)
```

Use `k = 60` as the initial RRF constant.

First-version filtering:

- scope permission filter
- empty chunk filter
- too-short chunk filter
- duplicate chunk merge
- `top_k` cap
- snippet truncation

Do not implement a reranker in the first version.

## Embeddings

Default embedding provider:

```text
provider = ollama
base_url = http://127.0.0.1:11434
model = bge-m3 or nomic-embed-text
```

Embedding is optional for retrieval availability. If Ollama is down, the embedding model is missing, the embedding call fails, or vector storage is unavailable, retrieval must degrade to BM25 and still return results when BM25 matches.

`retrieval_status` should make fallback explicit:

```json
{
  "mode": "bm25_only",
  "vector_available": false,
  "fallback_reason": "ollama_unavailable"
}
```

## API

### POST /api/rag/search

Purpose: return evidence chunks and citations. This endpoint does not require an LLM.

Request:

```json
{
  "query": "DeepSeek API 怎么配置？",
  "scopes": ["journal"],
  "top_k": 8,
  "debug": false
}
```

Response:

```json
{
  "query": "DeepSeek API 怎么配置？",
  "results": [],
  "citations": [],
  "retrieval_status": {
    "mode": "hybrid",
    "vector_available": true,
    "fallback_reason": null
  }
}
```

### POST /api/rag/answer

Purpose: retrieve evidence and synthesize a citation-backed answer with the current chat provider.

Request:

```json
{
  "question": "我之前关于 DeepSeek API 是怎么规划的？",
  "scopes": ["journal"],
  "top_k": 8,
  "debug": false
}
```

Response:

```json
{
  "answer": "根据记录，Kairos 近期默认 API 目标是 DeepSeek...",
  "citations": [],
  "confidence": "high",
  "retrieval_status": {
    "mode": "hybrid",
    "vector_available": true,
    "fallback_reason": null
  }
}
```

If no sufficient evidence is found, return a non-fabricated answer:

```json
{
  "answer": "我没有在已授权知识库中找到足够依据。",
  "citations": [],
  "confidence": "none",
  "retrieval_status": {
    "mode": "bm25_only",
    "vector_available": false,
    "fallback_reason": "ollama_unavailable"
  }
}
```

## Tool Adapter

Register tools:

```text
rag.search
rag.answer
```

`rag.search` returns chunks, citations, and retrieval status. Use it when Kairos needs evidence for its own reasoning.

`rag.answer` returns a finished evidence-based answer. Use it when the user asks a direct question over authorized knowledge.

Both tools must go through `ToolRouter`, `PermissionManager`, and `AuditLogger`.

Tool calls must require explicit `scopes`.

## Citation Schema

Use one citation shape for Journal, uploads, and Project Scopes:

```json
{
  "id": "citation-1",
  "scope": "journal",
  "document_id": "record-abc",
  "chunk_id": "chunk-abc",
  "title": "DeepSeek API 配置记录",
  "source_type": "record",
  "path": ".kairos/journal/artifacts/record-abc.md",
  "location": {
    "date": "2026-06-10",
    "page": null,
    "line_start": null,
    "line_end": null,
    "heading": null
  },
  "snippet": "...",
  "score": 0.72
}
```

Location fields vary by source:

- Diary/Record: date, heading, optional line range.
- Upload PDF: page and optional section/heading.
- Project file: path and line range.
- TXT/MD upload: line range and optional heading.

RAG answers must include citations. Without citations, `rag.answer` must not produce a confident factual answer.

## Debug Information

Default responses should stay clean for the UI.

Always return `retrieval_status`.

When `debug: true`, include per-result debug fields:

```json
{
  "bm25_rank": 3,
  "vector_rank": 1,
  "rrf_score": 0.031,
  "embedding_model": "bge-m3",
  "index_version": "..."
}
```

## Answer Synthesis

`rag.search` does not use an LLM.

`rag.answer` uses the currently configured chat provider from Settings, such as DeepSeek, Ollama, or another OpenAI-compatible provider. RAG must not bind itself to a specific chat model.

The answer prompt must enforce:

- answer only from retrieved citations,
- cite sources,
- say that evidence was not found when citations are insufficient,
- do not write retrieved content into Memory,
- do not expose hidden metadata or sensitive content outside authorized scopes.

If no chat provider is available, `rag.search` still works and `rag.answer` returns a clear model-unavailable error.

## Memory Boundary

RAG retrieval results do not automatically enter Memory.

RAG answers do not automatically enter Memory.

If the answer process reveals a durable user preference, routine, follow-up, or other long-term agent context, it must be saved as a Memory candidate and reviewed through the existing Memory approval boundary.

RAG answers may be captured into Journal/Record as user-facing knowledge.

## Index Updates

Use event-triggered indexing first:

- Journal/Record created or updated: reindex that artifact.
- Upload parsed successfully: index that upload.
- Project Scope: user manually starts index or refresh.
- Settings: provide rebuild index action.

Do not implement a file watcher in the first version.

## Observability

Add lightweight local retrieval events:

```text
.kairos/search/events.jsonl
```

Each search/answer event should record:

- timestamp
- query/question
- scopes
- mode: `bm25_only` or `hybrid`
- vector_available
- fallback_reason
- result_count
- top_document_ids
- duration_ms
- caller: `api` or `tool`
- error if any

Do not add Langfuse or another external observability system in the first version.

## Integration With Existing Kairos Modules

### FastAPI Backend

Add HTTP routes in the existing FastAPI app:

```text
POST /api/rag/search
POST /api/rag/answer
```

Keep route handlers thin. They should validate input, check scope access, call `RetrievalService`, and return typed JSON.

### KairosBackend Service Layer

Expose service methods such as:

```text
rag_search(...)
rag_answer(...)
rag_reindex(...)
```

The service layer should own access to `KairosPaths`, Settings, Journal artifacts, uploads, and Project Scope stores.

### Tool Runtime

Register `rag.search` and `rag.answer` in the native tool registry. The handlers should call `RetrievalService` through the same backend/runtime context, not HTTP.

### Journal

Journal artifacts are the default RAG source. Creating or updating Diary/Record artifacts should schedule or run reindexing for that artifact.

### Uploads

Add an uploads store under `.kairos/uploads/` or another Settings-configured storage path. Upload metadata should be indexed into `documents`, and parsed text should be chunked into `chunks`.

### Project Scopes

Project Scope search requires explicit `project:{scope_id}`. Indexing and search must verify that the scope exists, is enabled, and grants read access.

### Settings

Add settings for:

- embedding provider
- embedding base URL
- embedding model
- RAG index location
- rebuild index action

The default embedding provider is Ollama.

### Frontend

Frontend can use:

- search box in Journal/Record.
- "Ask from records" or equivalent action that calls `/api/rag/answer`.
- upload knowledge file flow for `.txt`, `.md`, `.pdf`.
- retrieval status display when vector search falls back to BM25.
- citations display with source links.

### Agent Loop

Kairos can call:

- `rag.search` when it needs evidence to complete a task.
- `rag.answer` when the user asks a direct question over authorized knowledge.

The Agent Loop remains the orchestrator. RAG is a service, not the agent brain.

## First Implementation Slice

1. Add `backend/src/kairos/retrieval/` with data models, SQLite store, chunking, BM25 search, RRF merge, and events log.
2. Index existing Journal artifacts into `.kairos/search/index.sqlite`.
3. Implement `/api/rag/search` for `journal` scope only.
4. Add `rag.search` tool for `journal` scope.
5. Add Ollama embedding adapter with BM25 fallback.
6. Add `/api/rag/answer` and `rag.answer` using the configured chat provider.
7. Add uploads for `.txt`, `.md`, `.pdf`.
8. Add explicit Project Scope indexing.

Keep each slice testable before moving to the next.
