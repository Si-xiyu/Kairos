import type { AgentEvent, BackendHealth, ChatResponse, Message, Session } from "../types";

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

export async function checkHealth(): Promise<BackendHealth> {
  return request<BackendHealth>("/api/health");
}

export async function bootstrapWorkspace(): Promise<void> {
  await request("/api/bootstrap", {
    method: "POST",
    body: {},
  });
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

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
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
        : `Kairos API request failed: ${response.status}`;
    throw new Error(message);
  }

  return payload as T;
}
