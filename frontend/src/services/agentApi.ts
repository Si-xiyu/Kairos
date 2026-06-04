import type {
  AgentEvent,
  AppState,
  BackendHealth,
  ChatResponse,
  DaemonStatus,
  JournalDocument,
  JournalSummary,
  Message,
  ProjectScopeData,
  Session,
  SettingsSummary,
  Todo,
  TodoData,
} from "../types";

const DEFAULT_API_BASE = "http://127.0.0.1:8765";

export const API_BASE =
  (import.meta.env.VITE_KAIROS_API_BASE as string | undefined)?.replace(/\/$/, "") ??
  DEFAULT_API_BASE;

type SessionsResponse = {
  sessions: Session[];
};

type SessionResponse = {
  session: Session;
};

type MessagesResponse = {
  session_id: string;
  messages: Message[];
};

type EventsResponse = {
  session_id: string;
  events: AgentEvent[];
};

type JournalsResponse = {
  journals: JournalSummary[];
};

type TodosResponse = {
  todos: Todo[];
};

type ApiRequestInit = {
  method?: string;
  body?: unknown;
};

class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function checkHealth(): Promise<BackendHealth> {
  return request<BackendHealth>("/api/health");
}

export async function bootstrapWorkspace(): Promise<void> {
  await request("/api/bootstrap", {
    method: "POST",
    body: {},
  });
}

export async function getAppState(): Promise<AppState> {
  return request<AppState>("/api/state");
}

export async function getDaemonStatus(): Promise<DaemonStatus | undefined> {
  return requestOptional<DaemonStatus>("/api/daemon/status");
}

export async function listSessions(): Promise<Session[]> {
  const response = await request<SessionsResponse>("/api/sessions");
  return response.sessions;
}

export async function createSession(id: string, title: string, summary = "New local Kairos session."): Promise<Session> {
  const response = await request<SessionResponse>("/api/sessions", {
    method: "POST",
    body: { id, title, summary },
  });
  return response.session;
}

export async function listMessages(sessionId: string): Promise<Message[]> {
  const response = await request<MessagesResponse>(`/api/sessions/${encodeURIComponent(sessionId)}/messages`);
  return response.messages;
}

export async function listAgentEvents(sessionId: string): Promise<AgentEvent[]> {
  const response = await request<EventsResponse>(`/api/sessions/${encodeURIComponent(sessionId)}/events`);
  return response.events;
}

export async function sendChatMessage(sessionId: string, text: string): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: {
      text,
      session: sessionId,
      autonomy: 3,
    },
  });
}

export async function listJournals(limit = 30): Promise<JournalSummary[]> {
  const response = await request<JournalsResponse>(`/api/journals?limit=${limit}`);
  return response.journals;
}

export async function readJournal(date: string): Promise<JournalDocument> {
  return request<JournalDocument>(`/api/journal?date=${encodeURIComponent(date)}`);
}

export async function saveJournal(date: string, content: string): Promise<JournalDocument> {
  return request<JournalDocument>("/api/journal", {
    method: "POST",
    body: { date, content },
  });
}

export async function listTodoData(): Promise<TodoData> {
  const response = await requestOptional<TodosResponse>("/api/todos");
  if (!response) {
    return {
      todos: [],
      lists: [],
      contractGap:
        "Missing backend endpoints: GET /api/todos, POST /api/todos, POST /api/todos/update, POST /api/todos/delete, POST /api/todos/complete, and Todo List CRUD.",
    };
  }
  return { todos: response.todos, lists: [] };
}

export async function createTodo(_todo: Omit<Todo, "id" | "completed">): Promise<never> {
  throw new Error("Todo persistence is pending backend Todo CRUD endpoints.");
}

export async function listProjectScopes(): Promise<ProjectScopeData> {
  const response = await requestOptional<ProjectScopeData>("/api/project-scopes");
  if (!response) {
    return {
      scopes: [],
      contractGap:
        "Missing backend endpoints: GET /api/project-scopes plus create, update, remove, and permission-summary routes.",
    };
  }
  return response;
}

export async function getSettingsSummary(appState?: AppState): Promise<SettingsSummary> {
  const response = await requestOptional<SettingsSummary>("/api/settings");
  if (response) {
    return response;
  }
  return {
    provider: "DeepSeek target via OpenAI-compatible provider",
    baseUrl: "Configured in backend environment or llm.json",
    model: "Backend default",
    storagePath: appState?.doctor.kairos_home,
    notifications: "pending",
    contractGap:
      "Missing backend settings endpoint for model provider, secrets, storage, notification policy, memory, project scopes, and provider configuration.",
  };
}

async function requestOptional<T>(path: string, init: ApiRequestInit = {}): Promise<T | undefined> {
  try {
    return await request<T>(path, init);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return undefined;
    }
    throw error;
  }
}

async function request<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: init.method ?? "GET",
    headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload !== null && "error" in payload
        ? String((payload as { error: unknown }).error)
        : typeof payload === "object" && payload !== null && "detail" in payload
          ? String((payload as { detail: unknown }).detail)
          : `Kairos API request failed: ${response.status}`;
    throw new ApiError(response.status, message);
  }

  return payload as T;
}
