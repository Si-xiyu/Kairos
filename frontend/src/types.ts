export type SessionStatus = "active" | "idle" | "archived";

export type Session = {
  id: string;
  title: string;
  summary: string;
  updatedAt: string;
  unreadCount?: number;
  status: SessionStatus;
};

export type MessageRole = "user" | "assistant" | "system";

export type MessageBlock =
  | {
      kind: "text";
      content: string;
    }
  | {
      kind: "markdown";
      content: string;
    }
  | {
      kind: "code";
      language: string;
      content: string;
    };

export type Message = {
  id: string;
  sessionId: string;
  role: MessageRole;
  author: string;
  createdAt: string;
  status?: "complete" | "streaming" | "pending";
  blocks: MessageBlock[];
};

export type AgentEventKind = "tool_call" | "tool_result" | "runtime" | "memory";

export type AgentEvent = {
  id: string;
  sessionId: string;
  kind: AgentEventKind;
  title: string;
  timestamp: string;
  status: "pending" | "running" | "ok" | "warning" | "error";
  summary: string;
  details: string;
};
