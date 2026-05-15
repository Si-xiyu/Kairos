# Claude Code 任务：Memory System 与 Life Log System

你负责 Kairos 的长期记忆与 Markdown 日记能力。

请先阅读：

1. `TECHNICAL_REQUIREMENTS.md`
2. `docs/parallel/COMMANDER_PLAN.md`
3. 本文档

## 写入范围

你可以修改：

```text
src/kairos/memory/**
src/kairos/lifelog/**
tests/test_memory_lifelog.py
templates/journal/**
docs/adr/*memory*
docs/adr/*lifelog*
```

不要修改：

```text
src/kairos/cli.py
src/kairos/config.py
src/kairos/messages.py
src/kairos/core/**
src/kairos/tools/**
src/kairos/permissions/**
pyproject.toml
```

如果你确实需要公共接口变更，请在最终报告中提出。

## 目标

实现一个不依赖 LLM、不依赖外部包的最小 Memory + Life Log 底座，供后续 Agent Core 调用。

本任务重点是本地文件格式、可读性、可测试性和边界清晰，不要求生成高质量 AI 文案。

## 具体需求

### 1. Memory 数据模型

实现类似以下概念：

```text
MemoryType:
  user
  feedback
  project
  reference
  life_pattern
  energy_pattern
  reflection_theme

MemoryEntry:
  name
  description
  type
  scope
  confidence
  created_at
  updated_at
  source
  content
```

建议文件：

```text
src/kairos/memory/model.py
```

### 2. Markdown frontmatter 存储

实现 `MemoryStore`：

```text
save(entry) -> Path
load(path_or_name) -> MemoryEntry
list(type=None) -> list[MemoryEntry]
delete(name) -> bool
rebuild_index() -> Path
```

正式 memory 存在：

```text
.kairos/memory/{type}/{name}.md
```

候选 memory 存在：

```text
.kairos/memory/candidates/{name}.md
```

索引：

```text
.kairos/memory/MEMORY.md
```

不要引入 PyYAML。frontmatter 可以用简单的 `key: value` 解析，值保持字符串即可。

### 3. Daily Journal

实现 `DailyJournalStore`：

```text
path_for(date) -> Path
exists(date) -> bool
create(date, sections=None) -> Path
append_fragment(date, heading, text) -> Path
read(date) -> str
```

日记路径：

```text
.kairos/journal/YYYY/MM/YYYY-MM-DD.md
```

默认模板应包含：

```text
# YYYY-MM-DD

## 今天发生了什么
## 我在想什么
## 做了哪些事情
## 情绪与能量
## 有价值的对话
## Kairos 的观察
## 明天可以轻轻推进的事
```

### 4. Weekly Review

实现 `WeeklyReviewStore` 的最小能力：

```text
path_for(start_date, end_date) -> Path
create(start_date, end_date, daily_notes) -> Path
read(start_date, end_date) -> str
```

路径：

```text
.kairos/reviews/weekly/YYYY-MM-DD_to_YYYY-MM-DD.md
```

内容可以先是确定性模板，不要求 AI 总结。

### 5. 测试

新增：

```text
tests/test_memory_lifelog.py
```

测试至少覆盖：

- 保存并读取 memory。
- rebuild index。
- candidate memory 不混入正式 memory，除非显式列出。
- 创建每日 journal。
- append fragment。
- 创建 weekly review。

测试必须使用临时目录，不污染真实 `.kairos/`。

## 验收标准

在你的 worktree 中运行：

```text
python scripts/smoke_check.py
python -m pytest tests/test_memory_lifelog.py
```

如果没有 pytest 环境，请至少说明未运行原因，并提供可用的手动验证命令。

## 设计注意

- 日记和 memory 是用户拥有的数据，格式必须人类可读。
- 不要把临时任务状态写入 memory。
- 不要保存密钥、token、密码。
- 不要做心理诊断式文案。
- 默认所有私人内容本地存储。

