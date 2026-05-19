import { mockAgentEvents, mockMessages, mockSessions } from "../data/mockData";
import type { AgentEvent, Message, Session } from "../types";

export async function listSessions(): Promise<Session[]> {
  return mockSessions;
}

export async function listMessages(sessionId: string): Promise<Message[]> {
  return mockMessages.filter((message) => message.sessionId === sessionId);
}

export async function listAgentEvents(sessionId: string): Promise<AgentEvent[]> {
  return mockAgentEvents.filter((event) => event.sessionId === sessionId);
}

// Future API boundary:
// - Replace these mocks with REST calls for historical state.
// - Add a WebSocket client that normalizes stream deltas, tool calls,
//   tool results, runtime status, and memory events into the local types.
// - Keep high-risk tool actions behind backend permission decisions.
