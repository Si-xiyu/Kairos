import type { AgentEvent, Message, Session } from "../types";

export const mockSessions: Session[] = [
  {
    id: "session-kairos-shell",
    title: "Kairos desktop shell",
    summary: "Shape the local-first Agent console and inspector workflow.",
    updatedAt: "09:42",
    unreadCount: 2,
    status: "active",
  },
  {
    id: "session-journal",
    title: "Nightly journal loop",
    summary: "Draft the reminder flow and Markdown handoff.",
    updatedAt: "Yesterday",
    status: "idle",
  },
  {
    id: "session-memory",
    title: "Memory candidates",
    summary: "Review local memory entries before promotion.",
    updatedAt: "Tue",
    status: "idle",
  },
  {
    id: "session-presence",
    title: "Presence engine",
    summary: "Heartbeat silence rules and delivery queue checks.",
    updatedAt: "Mon",
    status: "archived",
  },
];

export const mockMessages: Message[] = [
  {
    id: "msg-1",
    sessionId: "session-kairos-shell",
    role: "user",
    author: "You",
    createdAt: "09:37",
    blocks: [
      {
        kind: "text",
        content:
          "把前端改成 local-first Agent 控制台。我要左侧会话、中间消息、右侧 inspector，先用 mock 数据。",
      },
    ],
  },
  {
    id: "msg-2",
    sessionId: "session-kairos-shell",
    role: "assistant",
    author: "Kairos",
    createdAt: "09:38",
    blocks: [
      {
        kind: "markdown",
        content:
          "我会把 UI 拆成四个核心区域：\n\n- 会话列表负责选择工作上下文\n- 消息流负责呈现用户和 assistant 的对话\n- Agent Inspector 展示工具调用、结果、运行时状态和 memory 事件\n- 输入区保留 Enter 发送、Shift+Enter 换行和停止生成控制",
      },
      {
        kind: "code",
        language: "ts",
        content:
          "type AgentEvent = {\n  kind: 'tool_call' | 'tool_result' | 'runtime' | 'memory';\n  status: 'pending' | 'running' | 'ok' | 'warning' | 'error';\n};",
      },
    ],
  },
  {
    id: "msg-3",
    sessionId: "session-kairos-shell",
    role: "assistant",
    author: "Kairos",
    createdAt: "09:42",
    status: "streaming",
    blocks: [
      {
        kind: "text",
        content: "正在整理 mock 事件流和 Inspector 折叠交互...",
      },
    ],
  },
  {
    id: "msg-4",
    sessionId: "session-journal",
    role: "assistant",
    author: "Kairos",
    createdAt: "Yesterday",
    blocks: [
      {
        kind: "markdown",
        content:
          "今晚的日记提醒应该保持克制：先检查今天是否已有 journal，再判断勿扰和冷却时间，最后只投递一条可解释的 Windows 通知。",
      },
    ],
  },
  {
    id: "msg-5",
    sessionId: "session-memory",
    role: "user",
    author: "You",
    createdAt: "Tue",
    blocks: [
      {
        kind: "text",
        content: "把长期记忆候选和确认后的 memory 分开，避免自动写入私人画像。",
      },
    ],
  },
];

export const mockAgentEvents: AgentEvent[] = [
  {
    id: "event-1",
    sessionId: "session-kairos-shell",
    kind: "runtime",
    title: "Runtime ready",
    timestamp: "09:38:02",
    status: "ok",
    summary: "Local mock runtime initialized.",
    details:
      "Mode: mock\nTransport: none\nNext integration point: src/services/agentApi.ts",
  },
  {
    id: "event-2",
    sessionId: "session-kairos-shell",
    kind: "tool_call",
    title: "file.search",
    timestamp: "09:38:19",
    status: "ok",
    summary: "Scanned frontend structure.",
    details:
      "{\n  \"query\": \"frontend files\",\n  \"scope\": \"frontend/\",\n  \"risk\": \"low\"\n}",
  },
  {
    id: "event-3",
    sessionId: "session-kairos-shell",
    kind: "tool_result",
    title: "file.search result",
    timestamp: "09:38:20",
    status: "ok",
    summary: "Found static HTML/CSS/JS entry points.",
    details:
      "frontend/index.html\nfrontend/app.js\nfrontend/styles.css",
  },
  {
    id: "event-4",
    sessionId: "session-kairos-shell",
    kind: "memory",
    title: "Memory candidate",
    timestamp: "09:41:12",
    status: "warning",
    summary: "User prefers discussing technical direction before implementation.",
    details:
      "Candidate only. Do not promote without explicit confirmation. Scope: project/user preference.",
  },
  {
    id: "event-5",
    sessionId: "session-journal",
    kind: "tool_call",
    title: "journal.read",
    timestamp: "22:59:07",
    status: "pending",
    summary: "Waiting for permission boundary.",
    details:
      "The future backend should route this through the permission layer before touching local journal files.",
  },
];
