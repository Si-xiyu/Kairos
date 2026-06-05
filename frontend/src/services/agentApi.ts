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

type BackendJournalArtifactSummary = {
  id: string;
  type?: JournalArtifactKind;
  kind?: JournalArtifactKind;
  title: string;
  date?: string | null;
  path?: string;
  preview?: string;
  tags?: string[];
  updated_at?: string;
  updatedAt?: string;
  source?: string | { kind?: string; session_id?: string | null };
  legacy?: boolean;
  summary?: string | null;
};

type BackendJournalArtifact = BackendJournalArtifactSummary & {
  body?: string;
  content?: string;
  exists?: boolean;
};

type BackendJournalArtifactsResponse = {
  artifacts: BackendJournalArtifactSummary[];
};

type BackendJournalArtifactResponse = {
  artifact: BackendJournalArtifact;
};

type BackendSettingsResponse = {
  llm?: {
    provider?: string;
    suggested_provider?: string;
    base_url?: string | null;
    model?: string;
    api_key_configured?: boolean;
  };
  storage?: {
    kairos_home?: string;
    journal_path?: string;
    record_path?: string;
  };
  notifications?: {
    enabled?: boolean;
    quiet_hours_start?: string;
    quiet_hours_end?: string;
    daily_notification_budget?: number;
    default_channel?: string;
  };
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
  const response = await request<BackendJournalArtifactsResponse>(`/api/journal/artifacts?type=${encodeURIComponent(kind)}`);
  return response.artifacts.map(normalizeJournalArtifactSummary);
}

export async function readJournalArtifact(id: string): Promise<JournalArtifact> {
  const response = await request<BackendJournalArtifactResponse>(`/api/journal/artifacts/${encodeURIComponent(id)}`);
  return normalizeJournalArtifact(response.artifact);
}

export async function saveJournalArtifact(artifact: JournalArtifact): Promise<JournalArtifact> {
  const response = await request<BackendJournalArtifactResponse>("/api/journal/artifacts/update", {
    method: "POST",
    body: journalArtifactPayload(artifact),
  });
  return normalizeJournalArtifact(response.artifact);
}

export async function createJournalArtifact(input: {
  kind: JournalArtifactKind;
  title: string;
  content: string;
  tags: string[];
  date?: string;
}): Promise<JournalArtifact> {
  const response = await request<BackendJournalArtifactResponse>("/api/journal/artifacts", {
    method: "POST",
    body: {
      type: input.kind,
      title: input.title,
      body: input.content,
      tags: input.tags,
      date: input.date,
    },
  });
  return normalizeJournalArtifact(response.artifact);
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
    return normalizeSettings(await request<BackendSettingsResponse>("/api/settings"));
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
  const response = await request<BackendSettingsResponse>("/api/settings", {
    method: "POST",
    body: {
      llm: {
        provider: "openai-compatible",
        base_url: settings.baseUrl,
        model: settings.model,
        api_key: settings.apiKey,
      },
      storage: {
        journal_path: settings.storagePath,
      },
      notifications: {
        enabled: settings.notifications !== "disabled",
      },
    },
  });
  return normalizeSettings(response);
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

function normalizeJournalArtifactSummary(raw: BackendJournalArtifactSummary): JournalArtifactSummary {
  return {
    id: raw.id,
    kind: raw.kind ?? raw.type ?? "record",
    title: raw.title,
    date: raw.date ?? undefined,
    path: raw.path,
    preview: raw.preview,
    tags: raw.tags ?? [],
    updatedAt: raw.updatedAt ?? raw.updated_at,
    source: sourceLabel(raw.source),
    legacy: raw.legacy,
  };
}

function normalizeJournalArtifact(raw: BackendJournalArtifact): JournalArtifact {
  return {
    ...normalizeJournalArtifactSummary(raw),
    content: raw.content ?? raw.body ?? "",
    exists: raw.exists,
  };
}

function journalArtifactPayload(artifact: JournalArtifact): Record<string, unknown> {
  return {
    artifact_id: artifact.id,
    type: artifact.kind,
    title: artifact.title,
    body: artifact.content,
    tags: artifact.tags,
    date: artifact.date,
  };
}

function sourceLabel(source: BackendJournalArtifactSummary["source"]): string | undefined {
  if (!source) {
    return undefined;
  }
  if (typeof source === "string") {
    return source;
  }
  return [source.kind, source.session_id].filter(Boolean).join(":") || undefined;
}

function normalizeSettings(raw: BackendSettingsResponse): SettingsSummary {
  const llm = raw.llm ?? {};
  const storage = raw.storage ?? {};
  const notifications = raw.notifications ?? {};
  return {
    provider: llm.suggested_provider === "deepseek" ? "DeepSeek" : (llm.provider ?? "local"),
    baseUrl: llm.base_url ?? "",
    model: llm.model ?? "",
    apiKeyConfigured: llm.api_key_configured ?? false,
    storagePath: storage.journal_path ?? storage.kairos_home,
    notifications: notifications.enabled === false ? "disabled" : "enabled",
    notificationPolicy: [
      notifications.quiet_hours_start && notifications.quiet_hours_end
        ? `${notifications.quiet_hours_start}-${notifications.quiet_hours_end}`
        : "",
      notifications.daily_notification_budget !== undefined
        ? `${notifications.daily_notification_budget}/day`
        : "",
      notifications.default_channel,
    ].filter(Boolean).join(" | "),
    memoryPath: storage.kairos_home ? `${storage.kairos_home}\\memory` : undefined,
  };
}
