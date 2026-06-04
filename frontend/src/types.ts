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

export type ChatResponse = {
  outbound: Array<{
    channel: string;
    to: string;
    text: string;
  }>;
  observations: string[];
  session?: Session;
  messages?: Message[];
  events?: AgentEvent[];
};

export type BackendHealth = {
  ok: boolean;
  service: string;
};

export type JournalSummary = {
  date: string;
  path: string;
  title: string;
  preview: string;
  updated_at: string;
};

export type JournalDocument = {
  date: string;
  path: string;
  exists: boolean;
  content: string;
};

export type ScheduleItem = {
  id: string;
  name: string;
  enabled: boolean;
  next_run_at?: string | null;
  schedule?: Record<string, unknown>;
  payload?: Record<string, unknown>;
};

export type MemorySummary = {
  confirmed: number;
  candidates: number;
  total: number;
};

export type DaemonStatus = {
  running: boolean;
  interval_seconds?: number;
  last_tick_at?: string | null;
};

export type AppState = {
  app: {
    name: string;
    mode: string;
  };
  doctor: {
    initialized?: boolean;
    kairos_home?: string;
    journals?: number;
    memory_candidates?: number;
    schedules?: number;
    delivery_pending?: number;
    delivery_failed?: number;
    [key: string]: unknown;
  };
  today: {
    date: string;
    journal_exists: boolean;
    journal_path?: string;
  };
  recent_journals: JournalSummary[];
  memories: MemorySummary;
  schedules: {
    total: number;
    enabled: number;
    due: number;
    items: ScheduleItem[];
  };
  delivery: {
    pending: number;
    failed: number;
  };
  presence?: {
    session_id: string;
    events: number;
  };
  capabilities: {
    tools: number;
    skills: number;
    mcp_plugins: number;
  };
  sessions?: Session[];
};

export type ReminderLevel = "high" | "normal" | "none";
export type TodoKind = "event" | "task" | "reminder";

export type Todo = {
  id: string;
  title: string;
  notes?: string;
  listId?: string;
  completed: boolean;
  dueAt?: string;
  reminderAt?: string;
  reminderLevel: ReminderLevel;
  kind: TodoKind;
  source?: string;
};

export type TodoList = {
  id: string;
  name: string;
  color?: string;
};

export type TodoData = {
  todos: Todo[];
  lists: TodoList[];
  contractGap?: string;
};

export type ProjectScope = {
  id: string;
  path: string;
  name: string;
  permissions: {
    read: boolean;
    write: boolean;
    command: boolean;
  };
};

export type ProjectScopeData = {
  scopes: ProjectScope[];
  contractGap?: string;
};

export type SettingsSummary = {
  provider: string;
  baseUrl: string;
  model: string;
  storagePath?: string;
  notifications: "pending" | "enabled" | "disabled";
  contractGap?: string;
};
