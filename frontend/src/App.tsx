import { useEffect, useMemo, useState } from "react";
import { AgentInspector } from "./components/AgentInspector";
import { Composer } from "./components/Composer";
import { MessageStream } from "./components/MessageStream";
import { SessionSidebar } from "./components/SessionSidebar";
import { listAgentEvents, listMessages, listSessions } from "./services/agentApi";
import type { AgentEvent, Message, Session } from "./types";

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    async function loadInitialState() {
      const loadedSessions = await listSessions();
      const firstSessionId = loadedSessions[0]?.id ?? "";
      const [loadedMessages, loadedEvents] = await Promise.all([
        firstSessionId ? listMessages(firstSessionId) : Promise.resolve([]),
        firstSessionId ? listAgentEvents(firstSessionId) : Promise.resolve([]),
      ]);

      setSessions(loadedSessions);
      setActiveSessionId(firstSessionId);
      setMessages(loadedMessages);
      setEvents(loadedEvents);
    }

    loadInitialState();
  }, []);

  const filteredSessions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return sessions;
    }
    return sessions.filter(
      (session) =>
        session.title.toLowerCase().includes(normalized) ||
        session.summary.toLowerCase().includes(normalized),
    );
  }, [query, sessions]);

  const activeSession = sessions.find((session) => session.id === activeSessionId);
  const activeMessages = messages.filter((message) => message.sessionId === activeSessionId);
  const activeEvents = events.filter((event) => event.sessionId === activeSessionId);

  async function selectSession(sessionId: string) {
    setActiveSessionId(sessionId);
    setIsGenerating(false);
    const [nextMessages, nextEvents] = await Promise.all([listMessages(sessionId), listAgentEvents(sessionId)]);
    setMessages((current) => [
      ...current.filter((message) => message.sessionId !== sessionId),
      ...nextMessages,
    ]);
    setEvents((current) => [
      ...current.filter((event) => event.sessionId !== sessionId),
      ...nextEvents,
    ]);
  }

  function createSession() {
    const id = `session-${Date.now()}`;
    const session: Session = {
      id,
      title: "New local session",
      summary: "Draft a new Agent task.",
      updatedAt: "Now",
      status: "active",
    };
    setSessions((current) => [session, ...current]);
    setActiveSessionId(id);
    setDraft("");
  }

  function sendMessage() {
    const content = draft.trim();
    if (!content) {
      return;
    }

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      sessionId: activeSessionId,
      role: "user",
      author: "You",
      createdAt: "Now",
      blocks: [{ kind: "text", content }],
    };

    const assistantMessage: Message = {
      id: `msg-${Date.now()}-assistant`,
      sessionId: activeSessionId,
      role: "assistant",
      author: "Kairos",
      createdAt: "Now",
      status: "pending",
      blocks: [
        {
          kind: "text",
          content:
            "Mock response queued. The future WebSocket client will replace this with streaming assistant deltas.",
        },
      ],
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setSessions((current) =>
      current.map((session) =>
        session.id === activeSessionId
          ? { ...session, updatedAt: "Now", summary: content.slice(0, 72) }
          : session,
      ),
    );
    setDraft("");
    setIsGenerating(true);
  }

  return (
    <div className="app-shell">
      <SessionSidebar
        sessions={filteredSessions}
        activeSessionId={activeSessionId}
        query={query}
        onQueryChange={setQuery}
        onSelectSession={selectSession}
        onNewSession={createSession}
      />
      <div className="workbench">
        <MessageStream session={activeSession} messages={activeMessages} isGenerating={isGenerating} />
        <Composer
          value={draft}
          isGenerating={isGenerating}
          onChange={setDraft}
          onSend={sendMessage}
          onStop={() => setIsGenerating(false)}
        />
      </div>
      <AgentInspector events={activeEvents} />
    </div>
  );
}

export default App;
