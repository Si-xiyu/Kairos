# Kairos 并行实现总控计划

本文档最初用于三路并行开发；当前产品方向已经重置为 `docs/product/PRODUCT_TECHNICAL_PLAN.md` 中定义的本地优先个人工作/生活操作台。新的并行实现应优先使用前后端 agent 分工：

- Backend Agent：负责 FastAPI、本地存储、Todo/Journal/Today API、工具权限管道与 DeepSeek/OpenAI-compatible provider 配置。
- Frontend Agent：负责 React/Vite 桌面式 app shell、Today View、Todo、Journal、Project Scopes、Settings 与 contextual chat sidebar。
- Commander：负责主干方向、公共接口、最终合并和冲突裁决。

所有实例都必须先阅读：

1. `CONTEXT.md`
2. `docs/product/PRODUCT_TECHNICAL_PLAN.md`
3. 本文档
4. 自己的任务简报

当前任务简报：

```text
docs/parallel/BACKEND_AGENT_PROMPT.md
docs/parallel/FRONTEND_AGENT_PROMPT.md
```

## 当前主干状态

Commander 已建立最小项目骨架：

```text
pyproject.toml
README.md
AGENTS.md
CLAUDE.md
src/kairos/
  cli.py
  config.py
  messages.py
  core/
  tools/
  permissions/
  memory/
  lifelog/
  presence/
  channels/
  delivery/
scripts/smoke_check.py
```

主干已经定义的公共契约：

- `KairosPaths` 与 `ensure_workspace`
- `InboundMessage` 与 `OutboundMessage`
- `AgentLoop` 占位
- `SessionStore` 与 `SessionEvent`
- `ToolRegistry`、`ToolSpec`、`ToolResult`
- `ToolRouter` 与 `ToolExecutionResult`
- `PermissionManager`、`AutonomyLevel`
- `AuditLogger` 与 `AuditEvent`
- `build_native_registry`

其他 worker 应优先复用这些契约，不要平行创建另一套消息、路径或权限类型。

## Commander 负责范围

Commander 保留以下文件的最终所有权：

```text
pyproject.toml
README.md
AGENTS.md
CLAUDE.md
TECHNICAL_REQUIREMENTS.md
docs/parallel/**
src/kairos/cli.py
src/kairos/config.py
src/kairos/messages.py
src/kairos/core/**
src/kairos/tools/**
src/kairos/permissions/**
scripts/**
```

如果 worker 必须修改上述文件，应在最终报告中明确说明原因和建议 diff，而不是直接大改。

## Worker 任务分配

### Product Reset Round

Backend Agent 任务文件：

```text
docs/parallel/BACKEND_AGENT_PROMPT.md
```

Frontend Agent 任务文件：

```text
docs/parallel/FRONTEND_AGENT_PROMPT.md
```

建议顺序：

1. Backend Agent 先补稳定 API：Today、Todo、Journal artifact foundation、DeepSeek-oriented provider defaults。
2. Frontend Agent 可并行做 app shell 和受控 fallback，但不要把 mock 数据散落在组件里。
3. Commander 合并时优先检查 API contract 是否与 `docs/api/BACKEND_API.md` 和 frontend adapter 一致。
4. 前端发现缺口时在最终报告写 `Backend contract gaps`，不要直接大改后端。
5. 后端发现前端需要调整时在最终报告写 `Frontend contract notes`，不要直接大改前端。

### Round 2

Claude Code 下一轮任务：

```text
docs/parallel/ROUND2_CLAUDE_REFLECTION_MEMORY.md
```

Codex Worker 下一轮任务：

```text
docs/parallel/ROUND2_CODEX_SCHEDULER_DAEMON.md
```

两边开始前都应先同步 main，避免基于第一轮旧骨架继续写。

### Round 1

### Claude Code

任务文件：

```text
docs/parallel/CLAUDE_TASK_MEMORY_LIFELOG.md
```

写入范围：

```text
src/kairos/memory/**
src/kairos/lifelog/**
tests/test_memory_lifelog.py
templates/journal/**
docs/adr/*memory*
docs/adr/*lifelog*
```

### Codex Worker

任务文件：

```text
docs/parallel/CODEX_TASK_PRESENCE_DELIVERY.md
```

写入范围：

```text
src/kairos/presence/**
src/kairos/channels/**
src/kairos/delivery/**
tests/test_presence_delivery.py
docs/adr/*presence*
docs/adr/*delivery*
```

## 并行开发规则

1. 不修改别人拥有的模块。
2. 不进行全仓格式化。
3. 不引入外部依赖，除非任务简报明确允许。
4. 不修改 `pyproject.toml`，如确实需要依赖，在最终报告中提出。
5. 新增公共接口时，尽量放在自己模块内部；跨模块接口先用已有契约。
6. 测试必须能在仓库根目录运行。
7. 所有本地用户数据默认写入临时目录或 `.kairos/`，测试不得污染真实用户目录。

## 合并顺序

建议合并顺序：

1. Commander 主干骨架。
2. Claude Code 的 Memory/Life Log 分支。
3. Codex Worker 的 Presence/Delivery 分支。
4. Commander 统一接线、修正公共接口、补 smoke check。

原因：

- Memory/Life Log 较少依赖 Presence。
- Presence 可在 Life Log 接口存在后添加日记提醒事件。
- 最终 CLI/API 接线由 Commander 统一处理，避免两个 worker 同时改 CLI。

## Worker 最终报告格式

每个 worker 完成后，请在最终回复中包含：

```text
Changed files:
- path/to/file.py

Implemented:
- ...

Tests:
- command run
- result

Public interface requests:
- 如果需要 Commander 修改公共接口，在这里写清楚

Risks / TODO:
- ...
```

## Commander 合并检查清单

合并每个 worker 后，Commander 应检查：

- `git diff --name-only` 是否只包含该 worker 写入范围。
- 是否新增外部依赖。
- 是否破坏 `scripts/smoke_check.py`。
- 是否绕过权限系统。
- 是否把私人数据写入仓库。
- 是否存在 Windows 路径或编码问题。

最终至少运行：

```text
python scripts/smoke_check.py
python -m pytest tests/test_core_runtime.py
PYTHONPATH=src python -m kairos.cli status
PYTHONPATH=src python -m kairos.cli tools
PYTHONPATH=src python -m kairos.cli init --root <temp-dir>
```
