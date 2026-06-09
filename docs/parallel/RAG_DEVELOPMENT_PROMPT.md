# RAG Development Agent Prompt

You are the Kairos RAG development agent working on the `rag` branch. Your job is to implement Kairos's local evidence retrieval layer according to `docs/architecture/RAG_IMPLEMENTATION_PLAN.md`.

RAG is a service inside Kairos. It is not the agent brain and not an external paper QA platform.

## Read First

Read:

1. `CONTEXT.md`
2. `docs/product/PRODUCT_TECHNICAL_PLAN.md`
3. `docs/architecture/RAG_IMPLEMENTATION_PLAN.md`
4. `docs/parallel/COMMANDER_PLAN.md`
5. `docs/api/BACKEND_API.md`
6. `backend/src/kairos/lifelog/artifacts.py`
7. `backend/src/kairos/backend/scopes.py`
8. `backend/src/kairos/backend/service.py`
9. `backend/src/kairos/tools/native.py`
10. `backend/src/kairos/tools/advanced.py`

## Non-Negotiable Boundaries

Do not introduce:

- LangChain
- LangGraph
- PostgreSQL
- OpenSearch
- Redis
- Airflow
- broad filesystem indexing

Do not index:

- Memory
- raw Chat
- Settings
- Audit logs
- unrestricted filesystem content
- disabled Project Scopes
- sensitive files such as `.env`, keys, `.git`, `node_modules`, build outputs, virtual environments, binaries, large lock files

Agent RAG tools must go through `ToolRouter`, `PermissionManager`, and `AuditLogger`.

## Branch Goals

Implement RAG in small, testable slices.

### Slice 1: Retrieval Package and SQLite Store

Add:

```text
backend/src/kairos/retrieval/
```

Recommended modules:

```text
model.py
store.py
chunking.py
bm25.py
rrf.py
embeddings.py
service.py
events.py
```

Create index file:

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

Use SQLite FTS5 for BM25.

### Slice 2: Journal Indexing

Support `scope=["journal"]` first.

Index sources:

- Diary artifacts
- Record artifacts

Do not index raw chat. Do not index Memory.

Journal artifact create/update should trigger reindex or expose a callable reindex method.

### Slice 3: Search API

Add:

```text
POST /api/rag/search
```

Default API scopes may be `["journal"]`.

Request:

```json
{
  "query": "DeepSeek API",
  "scopes": ["journal"],
  "top_k": 8,
  "debug": false
}
```

Return:

- results/chunks,
- citations,
- retrieval_status,
- optional debug fields.

### Slice 4: rag.search Tool

Register:

```text
rag.search
```

Tool calls must require explicit `scopes`.

The tool handler should call `RetrievalService` directly, not HTTP.

### Slice 5: Ollama Embeddings and RRF

Default embedding settings:

```text
provider = ollama
base_url = http://127.0.0.1:11434
model = bge-m3 or nomic-embed-text
```

If embedding fails, return BM25 results with:

```json
{
  "mode": "bm25_only",
  "vector_available": false,
  "fallback_reason": "..."
}
```

Use RRF for hybrid merge:

```text
k = 60
```

### Slice 6: Answer API and Tool

Add:

```text
POST /api/rag/answer
rag.answer
```

`rag.answer` should:

- call search,
- synthesize with the current configured chat provider,
- require citations,
- refuse confident answers when evidence is insufficient,
- not write retrieved content into Memory.

If no chat provider is available, search still works and answer returns a clear error.

### Slice 7: Uploads

Add first-version uploads for:

- `.txt`
- `.md`
- `.pdf`

Upload = explicit authorization for `uploads` scope.

States:

- uploaded
- parsing
- indexed
- failed

Use a lightweight PDF dependency such as `pypdf` if needed. If adding a dependency, update `pyproject.toml` and tests.

### Slice 8: Project Scope Indexing

Support:

```text
project:{scope_id}
```

Only enabled Project Scopes with read permission can be indexed/searched.

Safe text extensions only:

```text
.md .txt .rst .py .ts .tsx .js .json .yaml .yml .toml
```

Do not auto-watch files in the first version. Provide manual index/refresh.

## Chunking Contract

Use:

```text
target_chars = 800
overlap_chars = 120
min_chars = 80
max_chars = 1200-1500
```

Store:

- heading
- line_start
- line_end
- page
- char_start
- char_end
- source_hash

No semantic chunking. No complex AST chunking.

## Citation Contract

Return citations with:

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

## Observability

Write retrieval events to:

```text
.kairos/search/events.jsonl
```

Record:

- timestamp
- query/question
- scopes
- mode
- vector_available
- fallback_reason
- result_count
- top_document_ids
- duration_ms
- caller: api or tool
- error if any

## Ownership

You may edit:

```text
backend/src/kairos/retrieval/**
backend/src/kairos/backend/fastapi_app.py
backend/src/kairos/backend/service.py
backend/src/kairos/backend/settings.py
backend/src/kairos/tools/advanced.py
backend/src/kairos/tools/native.py
docs/api/BACKEND_API.md
docs/architecture/RAG_IMPLEMENTATION_PLAN.md
tests/test_rag_*.py
tests/test_backend_api.py only for RAG route coverage
```

Avoid frontend files. Report frontend contract notes instead.

## Verification

Run focused RAG tests and full tests:

```powershell
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=(Resolve-Path .tmp).Path
$env:PYTEST_ADDOPTS='-p no:cacheprovider --basetemp=.tmp/pytest'
& 'E:\software\Miniconda\python.exe' -m pytest
```

Also run:

```powershell
git diff --check
```

## Final Report

Report:

```text
Changed files:

Implemented:

API/tool contracts:

Index schema:

Tests:

Frontend/backend contract notes:

Risks / TODO:
```
