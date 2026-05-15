# Round 2 Codex 任务：调度与 Daemon 基础设施

你负责把第一轮的 Presence/Delivery 底座推进到“可调度、可恢复、可由 daemon 驱动”的阶段。

开始前请先在你的 worktree 中同步 main：

```text
git fetch --all
git merge main
```

## 必读文件

1. `TECHNICAL_REQUIREMENTS.md`
2. `docs/parallel/COMMANDER_PLAN.md`
3. 本文档

## 写入范围

你可以修改：

```text
src/kairos/presence/**
src/kairos/channels/**
src/kairos/delivery/**
tests/test_scheduler_daemon.py
docs/adr/*scheduler*
docs/adr/*daemon*
```

不要修改：

```text
src/kairos/cli.py
src/kairos/core/**
src/kairos/tools/**
src/kairos/permissions/**
src/kairos/memory/**
src/kairos/lifelog/**
pyproject.toml
```

## 目标

实现一个不启动真实长期线程、不依赖外部包的调度与 daemon 核心逻辑。

这轮重点不是“真的后台运行”，而是让 Commander 下一轮可以把 `kairos daemon` 接上。

## 具体需求

### 1. Schedule 数据模型

建议文件：

```text
src/kairos/presence/schedule.py
```

实现：

```text
ScheduleKind:
  at
  every

Schedule:
  kind
  config

ScheduledJob:
  id
  name
  enabled
  schedule
  payload: PresenceEvent
  next_run_at
  consecutive_errors
```

不要引入 croniter。`cron` kind 留 TODO，不实现。

### 2. ScheduleStore

实现：

```text
ScheduleStore:
  load() -> list[ScheduledJob]
  save(jobs) -> None
  add(job) -> None
  update(job) -> None
```

文件路径：

```text
KairosPaths.schedules / "cron.json"
```

JSON 格式要人类可读。

### 3. Due 计算

实现：

```text
compute_next_run(job, now) -> datetime | None
due_jobs(jobs, now) -> list[ScheduledJob]
mark_success(job, now) -> ScheduledJob
mark_failure(job, now, max_errors=5) -> ScheduledJob
```

要求：

- `at`：到点后 due，一次性任务成功后可 disabled。
- `every`：按 `seconds` 间隔推进。
- 连续失败达到 5 次后自动 disabled。

### 4. DaemonTick

建议文件：

```text
src/kairos/presence/daemon.py
```

实现同步、单步 tick：

```text
DaemonRuntime.tick(now=None) -> dict
```

它应该：

- 读取 schedule store。
- 找到 due jobs。
- 将 payload 转换为 delivery queue 消息，或调用注入的 handler。
- 更新 job 成功/失败状态。

不要启动后台线程。不要 sleep。

### 5. ChannelManager

建议文件：

```text
src/kairos/channels/manager.py
```

实现：

```text
ChannelManager:
  register(channel)
  get(name)
  send(channel_name, to, text) -> bool
```

### 6. 测试

新增：

```text
tests/test_scheduler_daemon.py
```

覆盖：

- schedule store 保存/读取。
- `at` job due。
- `every` job next run。
- failure auto-disable。
- daemon tick 可以把 due payload 入队 delivery。
- channel manager 可以发送 CLI channel。

## 验收命令

```text
python scripts/smoke_check.py
python -m pytest tests/test_presence_delivery.py tests/test_scheduler_daemon.py
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

