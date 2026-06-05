import type {
  AgentEvent,
  AppState,
  BackendHealth,
  ChatResponse,
  DaemonStatus,
  JournalArtifact,
  JournalArtifactKind,
  JournalArtifactSummary,
  JournalDocument,
  JournalSummary,
  Message,
  ProjectScopeData,
  ProjectScope,
  Session,
  SettingsSummary,
  Todo,
  TodoData,
  TodoList,
  TodayData,
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

type TodoListsResponse = {
  lists: TodoList[];
};

type JournalArtifactsResponse = {
  artifacts: JournalArtifactSummary[];
};

type JournalArtifactResponse = {
  artifact: JournalArtifact;
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

export async function getToday(): Promise<TodayData> {
  return request<TodayData>("/api/today");
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

export async function listJournalArtifacts(kind: JournalArtifactKind): Promise<JournalArtifactSummary[]> {
  const response = await request<JournalArtifactsResponse>(`/api/journal-artifacts?kind=${encodeURIComponent(kind)}`);
  return response.artifacts;
}

export async function readJournalArtifact(id: string): Promise<JournalArtifact> {
  const response = await request<JournalArtifactResponse>(`/api/journal-artifacts/${encodeURIComponent(id)}`);
  return response.artifact;
}

export async function saveJournalArtifact(artifact: JournalArtifact): Promise<JournalArtifact> {
  const response = await request<JournalArtifactResponse>("/api/journal-artifacts/update", {
    method: "POST",
    body: artifact,
  });
  return response.artifact;
}

export async function createJournalArtifact(input: {
  kind: JournalArtifactKind;
  title: string;
  content: string;
  tags: string[];
  date?: string;
}): Promise<JournalArtifact> {
  const response = await request<JournalArtifactResponse>("/api/journal-artifacts", {
    method: "POST",
    body: input,
  });
  return response.artifact;
}

export async function listTodoData(): Promise<TodoData> {
  try {
    const [todosResponse, listsResponse] = await Promise.all([
      request<TodosResponse>("/api/todos"),
      request<TodoListsResponse>("/api/todo-lists"),
    ]);
    return { todos: todosResponse.todos, lists: listsResponse.lists };
  } catch (error) {
    return {
      todos: [],
      lists: [],
      error: apiErrorMessage(
        error,
        "Todo API unavailable. Expected GET /api/todos and GET /api/todo-lists.",
      ),
    };
  }
}

export async function createTodo(todo: Omit<Todo, "id" | "completed">): Promise<Todo> {
  const response = await request<{ todo: Todo }>("/api/todos", {
    method: "POST",
    body: todo,
  });
  return response.todo;
}

export async function updateTodo(todo: Todo): Promise<Todo> {
  const response = await request<{ todo: Todo }>("/api/todos/update", {
    method: "POST",
    body: todo,
  });
  return response.todo;
}

export async function deleteTodo(id: string): Promise<void> {
  await request("/api/todos/delete", {
    method: "POST",
    body: { id },
  });
}

export async function completeTodo(id: string, completed: boolean): Promise<Todo> {
  const response = await request<{ todo: Todo }>("/api/todos/complete", {
    method: "POST",
    body: { id, completed },
  });
  return response.todo;
}

export async function listProjectScopes(): Promise<ProjectScopeData> {
  try {
    return await request<ProjectScopeData>("/api/project-scopes");
  } catch (error) {
    return {
      scopes: [],
      error: apiErrorMessage(
        error,
        "Project Scope API unavailable. Expected GET /api/project-scopes plus create, update, delete, and disable routes.",
      ),
    };
  }
}

export async function createProjectScope(path: string): Promise<ProjectScope> {
  const response = await request<{ scope: ProjectScope }>("/api/project-scopes", {
    method: "POST",
    body: { path },
  });
  return response.scope;
}

export async function updateProjectScope(scope: ProjectScope): Promise<ProjectScope> {
  const response = await request<{ scope: ProjectScope }>("/api/project-scopes/update", {
    method: "POST",
    body: scope,
  });
  return response.scope;
}

export async function deleteProjectScope(id: string): Promise<void> {
  await request("/api/project-scopes/delete", {
    method: "POST",
    body: { id },
  });
}

export async function getSettingsSummary(appState?: AppState): Promise<SettingsSummary> {
  try {
    return await request<SettingsSummary>("/api/settings");
  } catch (error) {
    return {
      provider: "DeepSeek",
      baseUrl: "",
      model: "",
      apiKeyConfigured: false,
      storagePath: appState?.doctor.kairos_home,
      notifications: "pending",
      notificationPolicy: "",
      memoryPath: appState?.doctor.kairos_home ? `${appState.doctor.kairos_home}\\memory` : undefined,
      error: apiErrorMessage(error, "Settings API unavailable. Expected GET /api/settings and POST /api/settings."),
    };
  }
}

export async function saveSettings(settings: SettingsSummary & { apiKey?: string }): Promise<SettingsSummary> {
  return request<SettingsSummary>("/api/settings", {
    method: "POST",
    body: settings,
  });
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

function apiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return `${fallback} Backend returned ${error.status}: ${error.message}`;
  }
  if (error instanceof Error) {
    return `${fallback} ${error.message}`;
  }
  return fallback;
}
