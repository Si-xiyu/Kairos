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
  createTodo,
  getAppState,
  getDaemonStatus,
  getSettingsSummary,
  listAgentEvents,
  listJournals,
  listMessages,
  listProjectScopes,
  listSessions,
  listTodoData,
  readJournal,
  saveJournal,
  sendChatMessage,
} from "./services/agentApi";
import type {
  AgentEvent,
  AppState,
  DaemonStatus,
  JournalDocument,
  JournalSummary,
  Message,
  ProjectScopeData,
  ReminderLevel,
  Session,
  SettingsSummary,
  TodoData,
  TodoKind,
} from "./types";

type BackendStatus = "online" | "offline";
type ViewId = "today" | "todo" | "journal" | "scopes" | "settings" | "chat";

const views: Array<{ id: ViewId; label: string }> = [
  { id: "today", label: "Today" },
  { id: "todo", label: "Todo" },
  { id: "journal", label: "Journal" },
  { id: "scopes", label: "Project Scopes" },
  { id: "settings", label: "Settings" },
  { id: "chat", label: "Chat" },
];

const chatPlaceholders: Record<ViewId, string> = {
  today: "Ask Kairos to help with today, summarize open loops, or prepare the next action...",
  todo: "Ask Kairos to turn a commitment into a reliable Todo...",
  journal: "Ask Kairos to summarize, archive, or shape this Journal entry...",
  scopes: "Ask Kairos to frame local file work inside a Project Scope...",
  settings: "Ask Kairos about model, storage, notification, Memory, or provider settings...",
  chat: "Ask Kairos anything in the current local session...",
};

function App() {
  const [activeView, setActiveView] = useState<ViewId>("today");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isBooting, setIsBooting] = useState(true);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("offline");
  const [errorMessage, setErrorMessage] = useState("");
  const [appState, setAppState] = useState<AppState | undefined>();
  const [daemonStatus, setDaemonStatus] = useState<DaemonStatus | undefined>();
  const [journals, setJournals] = useState<JournalSummary[]>([]);
  const [activeJournal, setActiveJournal] = useState<JournalDocument | undefined>();
  const [journalDraft, setJournalDraft] = useState("");
  const [isSavingJournal, setIsSavingJournal] = useState(false);
  const [todoData, setTodoData] = useState<TodoData>({ todos: [], lists: [] });
  const [todoDraft, setTodoDraft] = useState({
    title: "",
    kind: "task" as TodoKind,
    reminderLevel: "normal" as ReminderLevel,
    dueAt: "",
    reminderAt: "",
  });
  const [todoNotice, setTodoNotice] = useState("");
  const [projectScopes, setProjectScopes] = useState<ProjectScopeData>({ scopes: [] });
  const [settings, setSettings] = useState<SettingsSummary | undefined>();

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
            "Use the contextual sidebar to work with Today, Todo, Journal, Project Scopes, and Settings.",
          );
          loadedSessions = [created];
        }

        const firstSessionId = loadedSessions[0]?.id ?? "";
        const [loadedMessages, loadedEvents, state, daemon, journalItems, todos, scopes] = await Promise.all([
          firstSessionId ? listMessages(firstSessionId) : Promise.resolve([]),
          firstSessionId ? listAgentEvents(firstSessionId) : Promise.resolve([]),
          getAppState(),
          getDaemonStatus(),
          listJournals(30),
          listTodoData(),
          listProjectScopes(),
        ]);
        const settingsSummary = await getSettingsSummary(state);
        const todayJournal = await readJournal(state.today.date);

        setSessions(loadedSessions);
        setActiveSessionId(firstSessionId);
        setMessages(loadedMessages);
        setEvents(loadedEvents);
        setAppState(state);
        setDaemonStatus(daemon);
        setJournals(journalItems);
        setActiveJournal(todayJournal);
        setJournalDraft(todayJournal.content);
        setTodoData(todos);
        setProjectScopes(scopes);
        setSettings(settingsSummary);
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
    const [nextSessions, nextMessages, nextEvents, state, daemon] = await Promise.all([
      listSessions(),
      listMessages(sessionId),
      listAgentEvents(sessionId),
      getAppState(),
      getDaemonStatus(),
    ]);
    setSessions(nextSessions);
    setAppState(state);
    setDaemonStatus(daemon);
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
      const session = await createBackendSession(id, "New local session", "A fresh Kairos conversation.");
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

  async function openJournal(date: string) {
    try {
      const journal = await readJournal(date);
      setActiveJournal(journal);
      setJournalDraft(journal.content);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to open Journal.");
    }
  }

  async function persistJournal() {
    if (!activeJournal) {
      return;
    }
    setIsSavingJournal(true);
    try {
      const saved = await saveJournal(activeJournal.date, journalDraft);
      const nextJournals = await listJournals(30);
      setActiveJournal(saved);
      setJournalDraft(saved.content);
      setJournals(nextJournals);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to save Journal.");
    } finally {
      setIsSavingJournal(false);
    }
  }

  async function submitTodoDraft() {
    if (!todoDraft.title.trim()) {
      return;
    }
    try {
      await createTodo({
        title: todoDraft.title.trim(),
        kind: todoDraft.kind,
        reminderLevel: todoDraft.reminderLevel,
        dueAt: todoDraft.dueAt || undefined,
        reminderAt: todoDraft.reminderAt || undefined,
      });
    } catch (error) {
      setTodoNotice(error instanceof Error ? error.message : "Todo backend contract is not available yet.");
    }
  }

  const mainTitle = views.find((view) => view.id === activeView)?.label ?? "Today";

  return (
    <div className="desktop-shell">
      <aside className="primary-nav" aria-label="Primary navigation">
        <div className="brand-block">
          <p className="app-kicker">Kairos</p>
          <h1>Personal Console</h1>
        </div>
        <nav className="nav-list">
          {views.map((view) => (
            <button
              className={`nav-item ${activeView === view.id ? "is-active" : ""}`}
              type="button"
              key={view.id}
              onClick={() => setActiveView(view.id)}
            >
              {view.label}
            </button>
          ))}
        </nav>
        <div className="nav-footer">
          <span className={`status-light ${backendStatus}`} />
          <div>
            <strong>{backendStatus === "online" ? "Backend online" : "Backend offline"}</strong>
            <code>{API_BASE}</code>
          </div>
        </div>
      </aside>

      <main className="view-shell">
        <header className="topbar">
          <div>
            <p className="app-kicker">Current View</p>
            <h2>{mainTitle}</h2>
          </div>
          <div className="status-cluster" aria-label="Kairos status">
            <StatusPill label="Model" value={settings?.model ?? "Backend default"} />
            <StatusPill label="Daemon" value={daemonStatus?.running ? "Running" : "Idle"} />
            <StatusPill label="Memory" value={`${appState?.memories.candidates ?? 0} candidates`} />
          </div>
        </header>

        {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
        {isBooting ? <div className="loading-panel">Connecting to Kairos...</div> : renderActiveView()}
      </main>

      <aside className="context-chat" aria-label="Contextual chat sidebar">
        <div className="context-chat-header">
          <div>
            <p className="app-kicker">Contextual Chat</p>
            <h2>{mainTitle}</h2>
          </div>
          <button className="icon-button" type="button" aria-label="New session" onClick={createSession}>
            +
          </button>
        </div>
        <MessageStream session={activeSession} messages={activeMessages} isGenerating={isGenerating} />
        <Composer
          value={draft}
          isGenerating={isGenerating}
          placeholder={chatPlaceholders[activeView]}
          onChange={setDraft}
          onSend={sendMessage}
          onStop={() => setIsGenerating(false)}
        />
      </aside>
    </div>
  );

  function renderActiveView() {
    if (activeView === "today") {
      return <TodayView state={appState} daemonStatus={daemonStatus} journals={journals} sessions={sessions} />;
    }
    if (activeView === "todo") {
      return (
        <TodoView
          todoData={todoData}
          todoDraft={todoDraft}
          notice={todoNotice}
          onDraftChange={setTodoDraft}
          onSubmit={submitTodoDraft}
        />
      );
    }
    if (activeView === "journal") {
      return (
        <JournalView
          journals={journals}
          activeJournal={activeJournal}
          draft={journalDraft}
          isSaving={isSavingJournal}
          onOpen={openJournal}
          onDraftChange={setJournalDraft}
          onSave={persistJournal}
        />
      );
    }
    if (activeView === "scopes") {
      return <ProjectScopesView data={projectScopes} />;
    }
    if (activeView === "settings") {
      return <SettingsView settings={settings} appState={appState} />;
    }
    return (
      <div className="chat-workspace">
        <SessionSidebar
          sessions={filteredSessions}
          activeSessionId={activeSessionId}
          query={query}
          onQueryChange={setQuery}
          onSelectSession={selectSession}
          onNewSession={createSession}
        />
        <AgentInspector events={activeEvents} backendStatus={backendStatus} />
      </div>
    );
  }
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="status-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TodayView({
  state,
  daemonStatus,
  journals,
  sessions,
}: {
  state?: AppState;
  daemonStatus?: DaemonStatus;
  journals: JournalSummary[];
  sessions: Session[];
}) {
  const today = state?.today.date ?? new Date().toISOString().slice(0, 10);
  const scheduleItems = state?.schedules.items ?? [];

  return (
    <section className="view-grid today-view">
      <div className="view-intro">
        <div>
          <p className="app-kicker">Today View</p>
          <h3>{formatDate(today)}</h3>
        </div>
        <span className={`journal-state ${state?.today.journal_exists ? "ready" : "pending"}`}>
          {state?.today.journal_exists ? "Diary exists" : "Diary not started"}
        </span>
      </div>

      <div className="metric-row">
        <Metric label="Schedules due" value={String(state?.schedules.due ?? 0)} />
        <Metric label="Delivery pending" value={String(state?.delivery.pending ?? 0)} />
        <Metric label="Memory candidates" value={String(state?.memories.candidates ?? 0)} />
        <Metric label="Tools" value={String(state?.capabilities.tools ?? 0)} />
      </div>

      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Due And Upcoming</h3>
          <span>{state?.schedules.enabled ?? 0} enabled</span>
        </header>
        <div className="item-list">
          {scheduleItems.length ? (
            scheduleItems.map((item) => (
              <article className="list-item" key={item.id}>
                <strong>{item.name}</strong>
                <span>{item.enabled ? "Enabled" : "Paused"}</span>
              </article>
            ))
          ) : (
            <EmptyState title="No due schedules" detail="Todo endpoints will provide reliable reminders here." />
          )}
        </div>
      </section>

      <section className="panel">
        <header className="panel-header">
          <h3>Recent Journals</h3>
          <span>{journals.length}</span>
        </header>
        <div className="item-list">
          {journals.slice(0, 4).map((journal) => (
            <article className="list-item" key={journal.path}>
              <strong>{journal.title}</strong>
              <span>{journal.preview || journal.date}</span>
            </article>
          ))}
          {!journals.length ? <EmptyState title="No journals yet" detail="Diary and Record artifacts will appear here." /> : null}
        </div>
      </section>

      <section className="panel">
        <header className="panel-header">
          <h3>Recent Sessions</h3>
          <span>{sessions.length}</span>
        </header>
        <div className="item-list">
          {sessions.slice(0, 4).map((session) => (
            <article className="list-item" key={session.id}>
              <strong>{session.title}</strong>
              <span>{session.summary}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Companion Nudge</h3>
          <span>{daemonStatus?.running ? "Daemon running" : "Quiet"}</span>
        </header>
        <p className="muted-copy">
          Low-level Companion Nudge data is not exposed as a dedicated frontend endpoint yet. Presence events are
          available through the Kairos session stream.
        </p>
      </section>
    </section>
  );
}

function TodoView({
  todoData,
  todoDraft,
  notice,
  onDraftChange,
  onSubmit,
}: {
  todoData: TodoData;
  todoDraft: {
    title: string;
    kind: TodoKind;
    reminderLevel: ReminderLevel;
    dueAt: string;
    reminderAt: string;
  };
  notice: string;
  onDraftChange: (draft: {
    title: string;
    kind: TodoKind;
    reminderLevel: ReminderLevel;
    dueAt: string;
    reminderAt: string;
  }) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="view-grid todo-view">
      <div className="view-intro">
        <div>
          <p className="app-kicker">Reliable Commitments</p>
          <h3>Todo List</h3>
        </div>
        <div className="segmented-control" aria-label="Todo filters">
          <button className="is-active" type="button">Open</button>
          <button type="button">Due</button>
          <button type="button">Done</button>
        </div>
      </div>

      <section className="panel form-panel">
        <header className="panel-header">
          <h3>Create Todo</h3>
          <span>Manual entry</span>
        </header>
        <label className="field">
          <span>Title</span>
          <input
            value={todoDraft.title}
            onChange={(event) => onDraftChange({ ...todoDraft, title: event.target.value })}
            placeholder="Submit assignment, call dentist, prepare notes..."
          />
        </label>
        <div className="field-row">
          <label className="field">
            <span>Kind</span>
            <select
              value={todoDraft.kind}
              onChange={(event) => onDraftChange({ ...todoDraft, kind: event.target.value as TodoKind })}
            >
              <option value="task">Task</option>
              <option value="event">Event</option>
              <option value="reminder">Reminder</option>
            </select>
          </label>
          <label className="field">
            <span>Reminder Level</span>
            <select
              value={todoDraft.reminderLevel}
              onChange={(event) =>
                onDraftChange({ ...todoDraft, reminderLevel: event.target.value as ReminderLevel })
              }
            >
              <option value="high">High</option>
              <option value="normal">Normal</option>
              <option value="none">None</option>
            </select>
          </label>
        </div>
        <div className="field-row">
          <label className="field">
            <span>Due Time</span>
            <input
              value={todoDraft.dueAt}
              onChange={(event) => onDraftChange({ ...todoDraft, dueAt: event.target.value })}
              type="datetime-local"
            />
          </label>
          <label className="field">
            <span>Reminder Time</span>
            <input
              value={todoDraft.reminderAt}
              onChange={(event) => onDraftChange({ ...todoDraft, reminderAt: event.target.value })}
              type="datetime-local"
            />
          </label>
        </div>
        <button className="primary-control" type="button" onClick={onSubmit} disabled={!todoDraft.title.trim()}>
          Save Todo
        </button>
        {notice ? <p className="contract-gap">{notice}</p> : null}
      </section>

      <section className="panel todo-list-panel">
        <header className="panel-header">
          <h3>Todos</h3>
          <span>{todoData.todos.length}</span>
        </header>
        {todoData.contractGap ? <p className="contract-gap">{todoData.contractGap}</p> : null}
        <div className="item-list">
          {todoData.todos.map((todo) => (
            <article className="list-item" key={todo.id}>
              <strong>{todo.title}</strong>
              <span>{todo.kind} / {todo.reminderLevel}</span>
            </article>
          ))}
          {!todoData.todos.length ? (
            <EmptyState title="No persisted todos" detail="The UI is ready, but backend Todo CRUD is not exposed yet." />
          ) : null}
        </div>
      </section>
    </section>
  );
}

function JournalView({
  journals,
  activeJournal,
  draft,
  isSaving,
  onOpen,
  onDraftChange,
  onSave,
}: {
  journals: JournalSummary[];
  activeJournal?: JournalDocument;
  draft: string;
  isSaving: boolean;
  onOpen: (date: string) => void;
  onDraftChange: (value: string) => void;
  onSave: () => void;
}) {
  return (
    <section className="journal-layout">
      <aside className="journal-sidebar">
        <div className="segmented-control">
          <button className="is-active" type="button">Diary</button>
          <button type="button" disabled>Record</button>
        </div>
        <div className="item-list">
          {journals.map((journal) => (
            <button
              className={`journal-row ${journal.date === activeJournal?.date ? "is-active" : ""}`}
              type="button"
              key={journal.path}
              onClick={() => onOpen(journal.date)}
            >
              <strong>{journal.title}</strong>
              <span>{journal.date}</span>
            </button>
          ))}
        </div>
        <p className="contract-gap">Record artifact endpoints are not exposed yet; current backend supports Diary-like daily journals.</p>
      </aside>

      <section className="journal-editor">
        <header className="panel-header">
          <div>
            <p className="app-kicker">Diary</p>
            <h3>{activeJournal?.date ?? "No Journal selected"}</h3>
          </div>
          <button className="primary-control" type="button" onClick={onSave} disabled={!activeJournal || isSaving}>
            {isSaving ? "Saving" : "Save"}
          </button>
        </header>
        <textarea
          className="markdown-editor"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder="# Today's Diary"
        />
      </section>
    </section>
  );
}

function ProjectScopesView({ data }: { data: ProjectScopeData }) {
  return (
    <section className="view-grid">
      <div className="view-intro">
        <div>
          <p className="app-kicker">Scope Permission</p>
          <h3>Project Scopes</h3>
        </div>
        <button className="secondary-control" type="button" disabled>Add Scope</button>
      </div>
      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Attached Directories</h3>
          <span>{data.scopes.length}</span>
        </header>
        {data.contractGap ? <p className="contract-gap">{data.contractGap}</p> : null}
        <div className="item-list">
          {data.scopes.map((scope) => (
            <article className="list-item" key={scope.id}>
              <strong>{scope.name}</strong>
              <span>{scope.path}</span>
            </article>
          ))}
          {!data.scopes.length ? (
            <EmptyState
              title="No Project Scopes attached"
              detail="Project Scopes will define where Kairos may read, write, and run approved commands."
            />
          ) : null}
        </div>
      </section>
    </section>
  );
}

function SettingsView({ settings, appState }: { settings?: SettingsSummary; appState?: AppState }) {
  return (
    <section className="view-grid settings-view">
      <div className="view-intro">
        <div>
          <p className="app-kicker">Local-first Trust</p>
          <h3>Settings</h3>
        </div>
      </div>
      <section className="panel">
        <header className="panel-header">
          <h3>Model Provider</h3>
          <span>Near-term default</span>
        </header>
        <ReadOnlyField label="Provider" value={settings?.provider ?? "DeepSeek target"} />
        <ReadOnlyField label="Base URL" value={settings?.baseUrl ?? "Backend configured"} />
        <ReadOnlyField label="Model" value={settings?.model ?? "Backend default"} />
      </section>
      <section className="panel">
        <header className="panel-header">
          <h3>Storage</h3>
          <span>Local</span>
        </header>
        <ReadOnlyField label="Kairos Home" value={settings?.storagePath ?? appState?.doctor.kairos_home ?? "Pending"} />
        <ReadOnlyField label="Journals" value={`${appState?.doctor.journals ?? 0} files`} />
        <ReadOnlyField label="Memory Candidates" value={`${appState?.memories.candidates ?? 0}`} />
      </section>
      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Configuration Areas</h3>
          <span>Pending backend settings</span>
        </header>
        <div className="settings-grid">
          <ReadOnlyField label="Notifications" value={settings?.notifications ?? "pending"} />
          <ReadOnlyField label="Memory Management" value="Review entry point pending" />
          <ReadOnlyField label="Project Scope" value="Permission editor pending" />
          <ReadOnlyField label="MCP/Search/Weather" value="Provider controls pending" />
        </div>
        {settings?.contractGap ? <p className="contract-gap">{settings.contractGap}</p> : null}
      </section>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <label className="field read-only-field">
      <span>{label}</span>
      <input value={value} readOnly />
    </label>
  );
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function formatDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export default App;
