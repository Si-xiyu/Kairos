import { useEffect, useMemo, useState } from "react";
import { AgentInspector } from "./components/AgentInspector";
import { Composer } from "./components/Composer";
import { MessageStream } from "./components/MessageStream";
import { SessionSidebar } from "./components/SessionSidebar";
import {
  API_BASE,
  bootstrapWorkspace,
  checkHealth,
  createSession as createBackendSession,
  listAgentEvents,
  listMessages,
  listSessions,
  sendChatMessage,
} from "./services/agentApi";
import type { AgentEvent, Message, Session } from "./types";

function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isBooting, setIsBooting] = useState(true);
  const [backendStatus, setBackendStatus] = useState<"online" | "offline">("offline");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    async function loadInitialState() {
      setIsBooting(true);
      try {
        await checkHealth();
        await bootstrapWorkspace();
        setBackendStatus("online");

        let loadedSessions = await listSessions();
        if (loadedSessions.length === 0) {
          const created = await createBackendSession(
            "default",
            "Kairos Console",
            "Start with /tool file.list path=. to exercise the local runtime.",
          );
          loadedSessions = [created];
        }

        const firstSessionId = loadedSessions[0]?.id ?? "";
        const [loadedMessages, loadedEvents] = await Promise.all([
          firstSessionId ? listMessages(firstSessionId) : Promise.resolve([]),
          firstSessionId ? listAgentEvents(firstSessionId) : Promise.resolve([]),
        ]);

        setSessions(loadedSessions);
        setActiveSessionId(firstSessionId);
        setMessages(loadedMessages);
        setEvents(loadedEvents);
        setErrorMessage("");
      } catch (error) {
        setBackendStatus("offline");
        setErrorMessage(error instanceof Error ? error.message : "Unable to reach Kairos backend.");
      } finally {
        setIsBooting(false);
      }
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

  async function refreshSession(sessionId: string) {
    const [nextSessions, nextMessages, nextEvents] = await Promise.all([
      listSessions(),
      listMessages(sessionId),
      listAgentEvents(sessionId),
    ]);
    setSessions(nextSessions);
    setMessages((current) => [
      ...current.filter((message) => message.sessionId !== sessionId),
      ...nextMessages,
    ]);
    setEvents((current) => [
      ...current.filter((event) => event.sessionId !== sessionId),
      ...nextEvents,
    ]);
  }

  async function createSession() {
    const id = `session-${Date.now()}`;
    try {
      const session = await createBackendSession(id, "New local session", "Draft a new Agent task.");
      setSessions((current) => [session, ...current]);
      setMessages((current) => current.filter((message) => message.sessionId !== id));
      setEvents((current) => current.filter((event) => event.sessionId !== id));
      setActiveSessionId(id);
      setDraft("");
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to create a Kairos session.");
    }
  }

  async function sendMessage() {
    const content = draft.trim();
    if (!content || !activeSessionId || isGenerating) {
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

    setMessages((current) => [...current, userMessage]);
    setSessions((current) =>
      current.map((session) =>
        session.id === activeSessionId
          ? { ...session, updatedAt: "Now", summary: content.slice(0, 72) }
          : session,
      ),
    );
    setDraft("");
    setIsGenerating(true);
    setErrorMessage("");

    try {
      await sendChatMessage(activeSessionId, content);
      await refreshSession(activeSessionId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Kairos backend did not respond.";
      setMessages((current) => [
        ...current,
        {
          id: `msg-${Date.now()}-error`,
          sessionId: activeSessionId,
          role: "system",
          author: "Kairos Runtime",
          createdAt: "Now",
          status: "complete",
          blocks: [{ kind: "text", content: message }],
        },
      ]);
      setErrorMessage(message);
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div className="app-shell">
      <div className={`backend-ribbon backend-${backendStatus}`}>
        <span>{backendStatus === "online" ? "Backend online" : "Backend offline"}</span>
        <code>{API_BASE}</code>
        {isBooting ? <em>Connecting...</em> : null}
      </div>
      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
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
      <AgentInspector events={activeEvents} backendStatus={backendStatus} />
    </div>
  );
}

export default App;
