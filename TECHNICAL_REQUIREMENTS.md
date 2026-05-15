# Kairos 技术需求与协作规格

本文档是 Kairos 项目的技术需求、架构边界与多实例协作约定。  
当并行运行多个 Codex 实例时，每个实例在开始实现前都应先阅读本文档，并严格遵守其中的模块边界、权限约束和实现顺序。

## 1. 产品定位

Kairos 不是单纯的 coding assistant，也不是只会问答的聊天机器人。

Kairos 的目标是成为一个本地优先、长期运行、有记忆、有主动性、能协助用户工作与自我反思的个人 AI 助手。它应同时具备：

- Claude Code / Codex 类 coding agent 的核心能力。
- 长期个人记忆、每日 Markdown 日记、周期性复盘与反思引导能力。
- OpenClaw 类 heartbeat、cron、channel、delivery queue 机制带来的主动存在感。
- 通用 AI 能力，例如联网搜索、天气、位置、饮食推荐、信息整理等。

一句话定位：

> Kairos 是一个以 coding agent 为核心、带长期个人记忆和现实世界工具接入的本地常驻个人 AI 助手。

## 2. 总体架构

Kairos 应被设计为本地常驻的 agent runtime，而不是单个聊天脚本。

推荐总体结构：

```text
Kairos
+- Agent Core             # 推理循环、工具调用、coding agent 主流程
+- Tool Runtime           # 文件、shell、搜索、MCP、天气、浏览器等工具
+- Memory System          # 用户偏好、反馈、项目记忆、长期画像
+- Life Log System        # 每日日记、周总结、月总结、反思对话
+- Presence Engine        # heartbeat、cron、主动提醒、任务回访
+- Channel Gateway        # CLI、Windows 通知、本地 Web、未来 IM/移动端
+- Permission Layer       # 权限、审计、确认、自治等级
+- Delivery Queue         # 主动消息可靠投递、重试、失败记录
+- Local Store            # Markdown、JSONL、SQLite、向量索引
```

核心原则：

- Agent Core 负责思考与执行。
- Presence Engine 负责主动性。
- Channel Gateway 负责输入输出通道。
- Memory 和 Life Log 负责长期连续性。
- Permission Layer 必须横跨所有工具调用与主动行为。

## 3. 推荐技术栈

第一阶段优先使用 Python。

理由：

- `learn-claude-code` 和 `claw0-main` 的教学实现均以 Python 展示关键机制。
- Python 更适合快速搭建 agent loop、tool registry、scheduler、MCP client 与本地文件型存储。
- 桌面 UI 可以后置，先确保 runtime 正确。

建议技术选型：

```text
Core Runtime: Python 3.11+
CLI: Typer 或 Click
Local API: FastAPI
Scheduler: croniter 或 APScheduler
Storage: Markdown + JSONL + SQLite
Vector Search: 后续可选 LanceDB / Chroma / sqlite-vss
Desktop Notification: Windows Toast 通知
MCP: Python MCP client
Future Desktop UI: Tauri / Electron / Web UI
```

不要在 MVP 初期引入过重的 UI、云同步、复杂插件市场或多端同步。

## 4. 运行形态

Kairos 至少应支持两种运行模式：

```text
kairos chat
```

用于交互式对话、coding、工具调用、调试。

```text
kairos daemon
```

长期后台运行，负责：

- heartbeat 主动检查。
- cron 定时任务。
- Windows 通知。
- 晚间日记提醒。
- 周总结生成。
- delivery queue 重试。
- 本地 UI / CLI 请求接入。

用户主动输入永远优先于后台任务。后台任务不能抢占正在进行的用户对话。

## 5. 本地数据目录

建议所有本地状态默认放在项目或用户配置目录下的 `.kairos/` 中。  
如果未来支持全局模式，可再区分 project scope 与 user scope。

建议目录：

```text
.kairos/
+- config.toml
+- conversations/
|  +- 2026-05-15.jsonl
+- journal/
|  +- 2026/
|     +- 05/
|        +- 2026-05-15.md
+- memory/
|  +- MEMORY.md
|  +- user/
|  +- feedback/
|  +- project/
|  +- reference/
|  +- candidates/
+- reviews/
|  +- weekly/
|  +- monthly/
+- tasks/
|  +- tasks.jsonl
+- delivery/
|  +- pending/
|  +- failed/
+- schedules/
|  +- cron.json
+- audit/
   +- tool-calls.jsonl
```

存储原则：

- 人类可读、需要用户直接编辑的内容用 Markdown。
- 事件流、会话、审计日志用 JSONL。
- 查询索引、状态表、关系型数据可用 SQLite。
- 向量索引只能作为检索增强层，不能成为唯一事实来源。

## 6. Agent Core 需求

Agent Core 参考 `learn-claude-code` 的主线能力，但不复制任何不该复制的专有实现。

基础流程：

```text
User / Cron / Heartbeat / Channel message
        |
        v
InboundMessage
        |
        v
Session Resolver
        |
        v
Prompt Builder
        |
        v
LLM
        |
        v
Tool Call?
        |
        v
Permission Check
        |
        v
Tool Runtime
        |
        v
Observation
        |
        v
Loop until final
        |
        v
Channel Delivery
```

建议模块：

```text
AgentLoop
ToolRegistry
ToolRouter
PermissionManager
ContextManager
SkillRegistry
MemoryRetriever
PromptBuilder
SessionStore
```

Agent Core 必须支持：

- 文件读取、搜索、创建、修改、删除。
- shell 命令执行。
- diff 查看。
- 测试运行。
- conversation JSONL 持久化。
- context compact / summary。
- skill 发现与按需加载。
- native tools 与 MCP tools 的统一路由。
- 所有工具调用进入权限管道。

## 7. Tool Runtime 与 MCP

所有工具都必须通过统一的 registry 和 router 暴露，不允许绕过权限系统直接执行高风险动作。

工具至少包含以下元信息：

```text
name
description
input_schema
risk_level
handler
source        # native / mcp / plugin
```

MCP 工具命名建议：

```text
mcp__{server}__{tool}
```

示例：

```text
mcp__browser__open_tab
mcp__weather__current
mcp__search__web
```

MCP 工具虽然来自外部 server，但仍然必须经过：

```text
ToolRouter -> PermissionManager -> MCPClient -> ResultNormalizer
```

工具结果应标准化返回：

```json
{
  "source": "mcp",
  "server": "weather",
  "tool": "current",
  "status": "ok",
  "preview": "...",
  "data": {}
}
```

## 8. Skill 系统

Skill 是按需加载的任务说明包，不应全部塞入 system prompt。

建议结构：

```text
skills/
  code-review/
    SKILL.md
  git-workflow/
    SKILL.md
  journal-guide/
    SKILL.md
```

SkillRegistry 至少支持：

- 扫描可用 skill。
- 读取轻量 manifest。
- 按需加载完整正文。
- 将已加载 skill 注入当前上下文。

system prompt 中只暴露 skill 目录和简短说明。完整 skill 只有在模型或流程明确需要时才加载。

## 9. Memory System

Memory 不是聊天记录，也不是临时任务进度。  
Memory 只保存跨会话仍然有价值、且不容易从当前环境重新推断的信息。

基础 memory 类型：

```text
user       # 用户偏好
feedback   # 用户纠正过的行为和判断
project    # 项目背景、约定、非显然决策原因
reference  # 外部资源指针
```

长期个人助手还应支持从日记中提炼出的生活模式：

```text
life_pattern
energy_pattern
reflection_theme
```

但这些内容默认应先进入候选区，等待用户确认。

Memory 条目建议使用 Markdown + frontmatter：

```md
---
name: prefer_guided_design_before_code
description: User prefers discussing architecture before implementation
type: user
scope: private
confidence: 0.8
created_at: 2026-05-15
updated_at: 2026-05-15
source: journal/2026/05/2026-05-15.md
---

The user prefers discussing architecture and product shape before writing code.
```

Memory 原则：

- 用户可查看、编辑、删除。
- 私人记忆默认本地优先。
- 记忆不是绝对真相，只提供方向。
- 记忆必须考虑新鲜度、来源和置信度。
- 不保存密钥、密码、token、隐私凭据。
- 不把当前代码结构、临时 PR 状态、一次性任务进度写入长期 memory。

## 10. Life Log System

Life Log 是 Kairos 的核心差异化能力。

目标：

- 将用户每日与 Kairos 的重要聊天、工作、想法整理为 Markdown 日记。
- 通过多轮对话引导用户写日记或日记大纲。
- 周期性总结用户最近做了什么、什么带来能量、什么反复消耗、下一步可以怎么调整。
- 从日记中提炼长期记忆候选，但正式写入 memory 前应让用户确认。

每日文件建议：

```text
.kairos/journal/YYYY/MM/YYYY-MM-DD.md
```

日记模板：

```md
# YYYY-MM-DD

## 今天发生了什么

## 我在想什么

## 做了哪些事情

## 情绪与能量

## 有价值的对话

## Kairos 的观察

## 明天可以轻轻推进的事
```

周总结模板：

```md
# Weekly Review: YYYY-MM-DD - YYYY-MM-DD

## 这一周你做了什么

## 哪些事情给你能量

## 哪些事情反复消耗你

## 反复出现的主题

## Kairos 观察到的模式

## 下周可以调整什么
```

语气要求：

- 温和、清醒、具体。
- 不做心理诊断。
- 不道德绑架。
- 使用“我观察到一种可能的模式”，而不是“你就是这样的人”。
- 重要判断尽量链接到对应日期的日记或会话来源。

## 11. Presence Engine

Presence Engine 参考 OpenClaw 的 heartbeat / cron / channel / delivery 机制。

它的职责是让 Kairos 具有低频、克制、可解释的主动性。

### 11.1 Heartbeat

Heartbeat 定期醒来，检查是否有值得主动提醒的事件。

默认行为应是沉默。  
只有满足条件时才生成主动消息。

基础流程：

```text
Heartbeat tick
  -> should_run()
  -> build presence prompt
  -> run single agent turn
  -> response == HEARTBEAT_OK ? suppress : enqueue delivery
```

`should_run()` 至少检查：

- 是否处于用户设置的活跃时间。
- 是否处于勿扰模式。
- 是否超过冷却时间。
- 今日主动通知数量是否超限。
- 用户是否正在主动对话。
- 是否存在值得提醒的事件。

### 11.2 Cron

Cron 用于固定节奏的任务。

示例：

```json
{
  "jobs": [
    {
      "id": "nightly-journal",
      "name": "Nightly Journal Check",
      "enabled": true,
      "schedule": {"kind": "cron", "expr": "0 23 * * *"},
      "payload": {
        "kind": "presence_event",
        "event": "daily_journal_check"
      }
    },
    {
      "id": "weekly-review",
      "name": "Weekly Review",
      "enabled": true,
      "schedule": {"kind": "cron", "expr": "0 21 * * 0"},
      "payload": {
        "kind": "presence_event",
        "event": "weekly_review"
      }
    }
  ]
}
```

Cron job 连续失败多次后应自动禁用，并写入日志。

### 11.3 主动行为示例

任务回访：

```text
你昨天说想推进 Kairos 的主动提醒系统。现在有在碰它吗？要不要我帮你把下一步压成一个小任务？
```

日记提醒：

```text
今天还没有留下记录。要不要随便丢几个碎片给我，我帮你整理成日记？
```

午餐推荐：

```text
现在快到午饭时间了。要不要我结合天气、位置和你最近的口味，帮你挑一个今天比较合适的选择？
```

## 12. Channel Gateway

所有输入输出通道都应归一化为统一消息格式。

建议输入格式：

```text
InboundMessage
  text
  sender_id
  channel
  account_id
  peer_id
  is_group
  media
  raw
```

第一阶段建议支持：

- CLI channel。
- Windows toast notification channel。
- Local API / local web channel。

未来可扩展：

- Telegram。
- Discord。
- Slack。
- 手机端。
- 浏览器插件。

Agent Core 不应直接依赖具体平台 API。平台差异由 Channel Gateway 处理。

## 13. Delivery Queue

主动消息不能直接发送后就丢失状态。  
所有主动消息应先写入 delivery queue，再由 delivery runner 投递。

流程：

```text
Agent / Heartbeat / Cron
        |
        v
DeliveryQueue.enqueue()
        |
        v
write pending JSON atomically
        |
        v
DeliveryRunner send
        |
        +-- success -> ack
        +-- failure -> retry with backoff
```

要求：

- 入队先写磁盘，再尝试投递。
- 使用临时文件 + flush/fsync + atomic replace，避免半写文件。
- 失败后指数退避重试。
- 超过最大重试次数进入 `delivery/failed/`。
- 启动时扫描 pending 队列，恢复未完成投递。
- 通知过期后应丢弃或归档，不应无限重试。

## 14. Permission Layer 与自治等级

Kairos 可以更主动，但不能无限权限。

建议自治等级：

```text
0 passive              # 只回答用户问题
1 notify_only          # 可提醒，但不执行动作
2 draft_only           # 可生成草稿、日记、周报，但不改重要状态
3 low_risk_auto        # 可自动执行低风险本地动作
4 approved_scope_auto  # 可在用户预授权范围内自动执行
5 high_autonomy_agent  # 高自主任务代理，仍需审计和可中止
```

工具风险等级：

```text
low       # 读文件、读日记、生成草稿
medium    # 写日记、更新任务、本地搜索
high      # 修改项目文件、运行 shell、删除文件、联网发送
critical  # git push、外部发送、系统级修改、凭据相关操作
```

决策规则：

```text
tool risk + autonomy level + user policy -> allow / ask / deny
```

所有权限决策应写入审计日志。

高风险动作必须满足：

- 用户显式确认，或
- 用户提前配置了明确授权范围。

主动提醒不应绕过权限系统。例如，自动发送外部消息、修改代码、删除文件都不能因为来自 cron 或 heartbeat 就直接执行。

## 15. 现实世界工具能力

Kairos 最终应支持“今天中午吃什么”这类综合问题。

所需能力：

- 当前时间。
- 用户大致位置。
- 天气。
- 用户饮食偏好。
- 忌口、预算、交通方式、堂食/外卖偏好。
- 联网搜索附近餐厅。
- 结果来源说明。
- 用户反馈学习。

回答应结合现实条件与个人偏好，而不是泛泛推荐。

示例目标回答：

```text
今天有点冷，而且你最近说中午不想吃太油。我建议选附近的砂锅粥或牛肉面。砂锅粥更适合现在的天气，也比较轻；牛肉面更快，但可能偏咸。
```

这类现实工具应通过 Tool Runtime 或 MCP 接入，并经过权限系统。

## 16. MVP 实现顺序

建议按以下顺序推进。并行 Codex 实例应尽量领取互不冲突的模块。

### Phase 1: Runtime Skeleton

- 建立项目结构。
- 建立 `.kairos/` 数据目录。
- 加载 `config.toml`。
- 基础日志。
- CLI 入口。

### Phase 2: Agent Core

- Agent loop。
- Tool registry。
- Tool router。
- 文件读写搜索。
- shell 执行。
- conversation JSONL。
- 简单 prompt builder。

### Phase 3: Permission

- 工具风险等级。
- allow / ask / deny 决策。
- 审计日志。
- 自治等级配置。

### Phase 4: Skill 与 Memory

- SkillRegistry。
- `load_skill` 工具。
- Memory 文件格式。
- Memory index。
- MemoryRetriever。

### Phase 5: Life Log

- 每日 Markdown 日记生成。
- 引导式日记对话。
- 周总结生成。
- memory candidate 提取。

### Phase 6: Daemon 与 Presence

- `kairos daemon`。
- heartbeat。
- cron。
- presence event。
- HEARTBEAT_OK 沉默约定。

### Phase 7: Channel 与 Delivery

- CLI channel。
- Windows toast channel。
- delivery queue。
- retry / failed / recovery。

### Phase 8: MCP 与外部工具

- MCP client。
- MCP tool discovery。
- MCP tool routing。
- 搜索、天气、浏览器等工具接入。

### Phase 9: Desktop / Local UI

- 本地 Web UI 或 Tauri/Electron。
- 日记编辑。
- memory 管理。
- 任务与提醒配置。

## 17. 多 Codex 实例协作约定

多个 Codex 实例并行工作时，必须遵守以下约定。

### 17.1 开始前

每个实例开始工作前必须：

- 阅读本文档。
- 检查当前 git 状态。
- 明确自己负责的模块与文件范围。
- 不修改与自己任务无关的文件。
- 不重构他人正在工作的模块。

### 17.2 文件所有权

建议按模块拆分所有权：

```text
Agent Core worker:
  kairos/core/**
  kairos/tools/**

Memory/Life Log worker:
  kairos/memory/**
  kairos/lifelog/**
  templates/journal/**

Presence worker:
  kairos/presence/**
  kairos/scheduler/**

Channel/Delivery worker:
  kairos/channels/**
  kairos/delivery/**

Permission worker:
  kairos/permissions/**
  kairos/audit/**

CLI/API worker:
  kairos/cli/**
  kairos/api/**
```

如果文件结构尚未创建，首次创建者应尽量按上述边界建立目录。

### 17.3 修改原则

- 小步提交，小范围修改。
- 新增公共接口时更新相关文档或类型说明。
- 不进行大规模格式化，除非任务明确要求。
- 不删除他人新增内容，除非明确确认。
- 遇到设计冲突时先记录问题，不要强行覆盖。

### 17.4 测试要求

每个模块至少应有轻量测试或手动验证说明。

优先测试：

- 工具路由。
- 权限决策。
- JSONL 会话写入。
- Markdown 日记生成。
- heartbeat 是否会正确沉默。
- cron 是否能触发任务。
- delivery queue 是否能失败重试。

### 17.5 文档更新

当实现偏离本文档时，必须同步更新本文档或新增 ADR。

建议 ADR 目录：

```text
docs/adr/
```

ADR 命名：

```text
0001-use-python-runtime.md
0002-local-markdown-journal.md
```

## 18. 非目标

MVP 阶段暂不追求：

- 完整桌面应用。
- 移动端。
- 云同步。
- 多用户团队协作。
- 完整插件市场。
- 高度复杂的向量记忆系统。
- 自动执行高风险 coding 任务。
- 情绪诊断或医疗/心理治疗能力。

Kairos 可以进行温和反思引导，但不能假装是心理医生。

## 19. 第一版最小闭环

第一版最小闭环应是：

> 用户白天和 Kairos 聊天或写代码；Kairos 保存会话；晚上 23:00 后台检查今天有没有日记；如果没有，就发 Windows 通知；用户点开后进入引导式日记；最后生成一篇 Markdown 日记。

这个闭环一旦跑通，Kairos 就已经不是普通 coding assistant。  
它开始具有长期记忆、主动节奏和个人陪伴感。

## 20. 设计底线

Kairos 必须始终满足：

- 用户拥有自己的数据。
- 用户能查看、编辑、删除记忆与日记。
- 主动行为可解释、可关闭、可限频。
- 高风险动作必须经过权限系统。
- 私人内容默认本地优先。
- 记忆不能替代当前事实观察。
- Kairos 可以俏皮，但不能打扰、操控或越权。

