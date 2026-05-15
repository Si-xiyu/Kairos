# Codex Worker 任务：Presence Engine、Channel Gateway 与 Delivery Queue

你负责 Kairos 的主动性、通道与可靠投递能力。

请先阅读：

1. `TECHNICAL_REQUIREMENTS.md`
2. `docs/parallel/COMMANDER_PLAN.md`
3. 本文档

## 写入范围

你可以修改：

```text
src/kairos/presence/**
src/kairos/channels/**
src/kairos/delivery/**
tests/test_presence_delivery.py
docs/adr/*presence*
docs/adr/*delivery*
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

实现一个不依赖 LLM、不依赖外部包的最小主动性底座：

- channel 抽象。
- delivery queue 磁盘可靠投递。
- heartbeat `should_run()`。
- cron/presence event 的轻量数据模型。

本任务不要求真正弹 Windows toast，也不要求启动真实后台线程。优先实现可测试、可接线的核心逻辑。

## 具体需求

### 1. Channel Gateway

实现 channel 抽象：

```text
Channel:
  name
  send(to, text, **kwargs) -> bool
```

建议文件：

```text
src/kairos/channels/base.py
src/kairos/channels/cli.py
```

`CLIChannel.send()` 可以简单 print 并返回 True。

如实现 Windows 通知，请先做 stub：

```text
WindowsToastChannel.send() -> bool
```

不要引入第三方 toast 包。真实通知接线留给 Commander 后续决定。

### 2. Delivery Queue

实现磁盘队列：

```text
QueuedDelivery:
  id
  channel
  to
  text
  enqueued_at
  next_retry_at
  retry_count
  last_error
  expires_at

DeliveryQueue:
  enqueue(channel, to, text, expires_at=None) -> str
  load_pending(now=None) -> list[QueuedDelivery]
  ack(delivery_id) -> None
  fail(delivery_id, error, now=None) -> None
```

路径使用：

```text
KairosPaths.delivery_pending
KairosPaths.delivery_failed
```

写文件要求：

- 先写 `.tmp.*.json`。
- flush。
- 尽量 fsync。
- atomic replace 到 `{id}.json`。

失败重试：

```text
backoff: 5s, 25s, 120s, 600s
max_retries: 5
```

超过最大重试次数移入 failed。

### 3. Delivery Runner

实现不启动线程的同步 runner 方法即可：

```text
DeliveryRunner.process_once(now=None) -> dict
```

它读取 pending，到期则调用 `deliver_fn(channel, to, text)`。

成功 ack。失败 fail。

### 4. Presence / Heartbeat

实现 `HeartbeatPolicy` 与 `HeartbeatState`：

```text
HeartbeatPolicy:
  interval_seconds
  active_hours
  daily_notification_budget
  cooldown_seconds

HeartbeatState:
  last_run_at
  running
  notifications_today
  last_notification_at
```

实现：

```text
should_run(now, policy, state, user_active=True, do_not_disturb=False) -> tuple[bool, str]
```

规则至少包含：

- 勿扰则不运行。
- 未到 interval 不运行。
- 不在 active hours 不运行。
- 正在运行不运行。
- 今日通知预算耗尽不运行。
- cooldown 未结束不运行。

默认语义：心跳大多数时候沉默。

### 5. Cron/Payload 数据模型

实现轻量模型即可：

```text
PresenceEvent:
  kind
  event
  payload
```

不要实现完整 cron parser，也不要引入 croniter。Commander 后续统一接 scheduler。

### 6. 测试

新增：

```text
tests/test_presence_delivery.py
```

测试至少覆盖：

- enqueue 生成 pending 文件。
- process_once 成功后 ack 删除 pending。
- process_once 失败后 retry_count 增加。
- 超过最大重试进入 failed。
- should_run 对 interval、active hours、DND、budget、cooldown 的判断。

测试必须使用临时目录，不污染真实 `.kairos/`。

## 验收标准

在你的 worktree 中运行：

```text
python scripts/smoke_check.py
python -m pytest tests/test_presence_delivery.py
```

如果没有 pytest 环境，请至少说明未运行原因，并提供可用的手动验证命令。

## 设计注意

- 主动消息必须先进 delivery queue。
- 用户主动输入优先于 heartbeat。
- 不要让 heartbeat 直接执行高风险动作。
- 不要让通知无限重试。
- 不要引入真实 Windows GUI 调用，避免测试不稳定。

