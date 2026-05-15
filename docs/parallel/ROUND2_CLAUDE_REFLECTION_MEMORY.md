# Round 2 Claude Code 任务：引导式日记与记忆候选

你负责把第一轮的 Memory/LifeLog 底座推进到“能从会话事件生成日记草稿和长期记忆候选”的阶段。

开始前请先在你的 worktree 中同步 main：

```text
git fetch --all
git merge main
```

如果你的 worktree 里还有 `.claude/settings.local.json` 本地改动，不要提交它，也不要合入 main。

## 必读文件

1. `TECHNICAL_REQUIREMENTS.md`
2. `docs/parallel/COMMANDER_PLAN.md`
3. 本文档

## 写入范围

你可以修改：

```text
src/kairos/lifelog/**
src/kairos/memory/**
tests/test_reflection_memory_candidates.py
docs/adr/*reflection*
docs/adr/*memory-candidate*
```

不要修改：

```text
src/kairos/cli.py
src/kairos/core/**
src/kairos/tools/**
src/kairos/permissions/**
src/kairos/presence/**
src/kairos/channels/**
src/kairos/delivery/**
pyproject.toml
```

## 目标

实现一个不依赖 LLM 的“反思草稿层”，供后续模型接入。

它不需要写出很聪明的日记，但要把数据结构和流程打通：

```text
SessionEvent[] / text fragments
  -> DailyReflectionDraft
  -> Markdown journal section text
  -> MemoryCandidate[]
  -> MemoryStore candidates
```

## 具体需求

### 1. Reflection 数据模型

建议文件：

```text
src/kairos/lifelog/reflection.py
```

实现：

```text
ReflectionFragment:
  text
  source
  created_at
  tags

DailyReflectionDraft:
  journal_date
  happened
  thoughts
  actions
  energy
  valuable_conversations
  kairos_observations
  tomorrow
```

### 2. JournalDraftBuilder

实现：

```text
JournalDraftBuilder.from_fragments(journal_date, fragments) -> DailyReflectionDraft
DailyReflectionDraft.to_markdown_sections() -> dict[str, str]
```

可以使用简单启发式：

- 包含“做了/完成/实现/修复”归到 actions。
- 包含“想/觉得/希望/担心”归到 thoughts。
- 包含“有能量/开心/累/消耗”归到 energy。
- 其他归到 happened。

注意：这是 deterministic scaffolding，不是最终智能文案。

### 3. 将草稿写入 DailyJournalStore

实现函数：

```text
write_reflection_draft(store, draft) -> Path
```

它应调用现有 `DailyJournalStore.append_fragment`，不要直接重复写文件逻辑。

### 4. Memory Candidate Extractor

建议文件：

```text
src/kairos/memory/candidates.py
```

实现：

```text
MemoryCandidate:
  entry: MemoryEntry
  reason: str

MemoryCandidateExtractor.extract_from_draft(draft) -> list[MemoryCandidate]
save_candidates(store, candidates) -> list[Path]
```

简单规则即可：

- 如果多次出现“喜欢/偏好/不喜欢/以后”之类词，生成 `user` 或 `feedback` 候选。
- 如果出现“有能量/消耗/反复”，生成 `energy_pattern` 或 `reflection_theme` 候选。

候选必须存入 `.kairos/memory/candidates/`，不得直接进入正式 memory。

### 5. 测试

新增：

```text
tests/test_reflection_memory_candidates.py
```

覆盖：

- fragments 可以生成 draft。
- draft 可以写入 journal。
- candidate extractor 生成候选。
- save_candidates 写入 candidates 目录。
- candidate 不出现在 `MemoryStore.list()` 默认结果中。

## 验收命令

```text
python scripts/smoke_check.py
python -m pytest tests/test_memory_lifelog.py tests/test_reflection_memory_candidates.py
```

## 最终报告格式

```text
Changed files:
- ...

Implemented:
- ...

Tests:
- ...

Public interface requests:
- ...

Risks / TODO:
- ...
```

