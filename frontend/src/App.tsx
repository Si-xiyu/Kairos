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
  completeTodo,
  createJournalArtifact,
  createProjectScope,
  createTodo,
  deleteProjectScope,
  deleteTodo,
  getToday,
  getAppState,
  getDaemonStatus,
  getSettingsSummary,
  listAgentEvents,
  listJournalArtifacts,
  listJournals,
  listMessages,
  listProjectScopes,
  listSessions,
  listTodoData,
  readJournalArtifact,
  readJournal,
  saveJournalArtifact,
  saveJournal,
  saveSettings,
  sendChatMessage,
  updateProjectScope,
  updateTodo,
} from "./services/agentApi";
import type {
  AgentEvent,
  AppState,
  DaemonStatus,
  JournalArtifact,
  JournalArtifactKind,
  JournalArtifactSummary,
  JournalDocument,
  JournalSummary,
  Message,
  ProjectScope,
  ProjectScopeData,
  ReminderLevel,
  Session,
  SettingsSummary,
  TodoData,
  Todo,
  TodoKind,
  TodayData,
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
  const [todayData, setTodayData] = useState<TodayData | undefined>();
  const [journals, setJournals] = useState<JournalSummary[]>([]);
  const [activeJournal, setActiveJournal] = useState<JournalDocument | undefined>();
  const [journalDraft, setJournalDraft] = useState("");
  const [journalMode, setJournalMode] = useState<JournalArtifactKind>("diary");
  const [journalArtifacts, setJournalArtifacts] = useState<JournalArtifactSummary[]>([]);
  const [activeArtifact, setActiveArtifact] = useState<JournalArtifact | undefined>();
  const [journalTagsDraft, setJournalTagsDraft] = useState("");
  const [journalTitleDraft, setJournalTitleDraft] = useState("");
  const [journalPreview, setJournalPreview] = useState(false);
  const [journalNotice, setJournalNotice] = useState("");
  const [isSavingJournal, setIsSavingJournal] = useState(false);
  const [todoData, setTodoData] = useState<TodoData>({ todos: [], lists: [] });
  const [todoFilter, setTodoFilter] = useState<"open" | "due" | "done">("open");
  const [activeTodoListId, setActiveTodoListId] = useState("all");
  const [editingTodoId, setEditingTodoId] = useState("");
  const [todoDraft, setTodoDraft] = useState({
    title: "",
    notes: "",
    listId: "",
    kind: "task" as TodoKind,
    reminderLevel: "normal" as ReminderLevel,
    dueAt: "",
    reminderAt: "",
    source: "",
  });
  const [todoNotice, setTodoNotice] = useState("");
  const [projectScopes, setProjectScopes] = useState<ProjectScopeData>({ scopes: [] });
  const [scopeDraftPath, setScopeDraftPath] = useState("");
  const [scopeNotice, setScopeNotice] = useState("");
  const [settings, setSettings] = useState<SettingsSummary | undefined>();
  const [settingsDraft, setSettingsDraft] = useState<SettingsSummary & { apiKey?: string }>({
    provider: "DeepSeek",
    baseUrl: "",
    model: "",
    apiKeyConfigured: false,
    notifications: "pending",
    notificationPolicy: "",
  });
  const [settingsNotice, setSettingsNotice] = useState("");

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
        const [loadedMessages, loadedEvents, state, daemon, today, journalItems, artifactItems, todos, scopes] = await Promise.all([
          firstSessionId ? listMessages(firstSessionId) : Promise.resolve([]),
          firstSessionId ? listAgentEvents(firstSessionId) : Promise.resolve([]),
          getAppState(),
          getDaemonStatus(),
          getToday().catch((error) => ({
            date: new Date().toISOString().slice(0, 10),
            todos: [],
            journalArtifacts: [],
            pendingApprovals: [],
            recentSessions: [],
            error: error instanceof Error ? error.message : "GET /api/today is unavailable.",
          })),
          listJournals(30),
          listJournalArtifacts("diary").catch(() => []),
          listTodoData(),
          listProjectScopes(),
        ]);
        const settingsSummary = await getSettingsSummary(state);
        const todayJournal = await readJournal(state.today.date);
        const firstArtifact =
          artifactItems[0] ? await readJournalArtifact(artifactItems[0].id).catch(() => undefined) : legacyJournalToArtifact(todayJournal);

        setSessions(loadedSessions);
        setActiveSessionId(firstSessionId);
        setMessages(loadedMessages);
        setEvents(loadedEvents);
        setAppState(state);
        setDaemonStatus(daemon);
        setTodayData(today);
        setJournals(journalItems);
        setJournalArtifacts(artifactItems.length ? artifactItems : firstArtifact ? [firstArtifact] : []);
        setActiveJournal(todayJournal);
        setJournalDraft(todayJournal.content);
        setActiveArtifact(firstArtifact);
        setJournalTitleDraft(firstArtifact?.title ?? "");
        setJournalTagsDraft(firstArtifact?.tags.join(", ") ?? "");
        setTodoData(todos);
        setProjectScopes(scopes);
        setSettings(settingsSummary);
        setSettingsDraft(settingsSummary);
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
      const artifact = legacyJournalToArtifact(journal);
      setActiveJournal(journal);
      setActiveArtifact(artifact);
      setJournalDraft(journal.content);
      setJournalTitleDraft(artifact.title);
      setJournalTagsDraft(artifact.tags.join(", "));
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to open Journal.");
    }
  }

  async function switchJournalMode(mode: JournalArtifactKind) {
    setJournalMode(mode);
    setJournalNotice("");
    try {
      const artifacts = await listJournalArtifacts(mode);
      setJournalArtifacts(artifacts);
      if (artifacts[0]) {
        const artifact = await readJournalArtifact(artifacts[0].id);
        setActiveArtifact(artifact);
        setJournalDraft(artifact.content);
        setJournalTitleDraft(artifact.title);
        setJournalTagsDraft(artifact.tags.join(", "));
      } else {
        setActiveArtifact(undefined);
        setJournalDraft("");
        setJournalTitleDraft("");
        setJournalTagsDraft("");
      }
    } catch (error) {
      if (mode === "diary") {
        const legacyItems = journals.map(legacySummaryToArtifact);
        setJournalArtifacts(legacyItems);
        if (activeJournal) {
          const artifact = legacyJournalToArtifact(activeJournal);
          setActiveArtifact(artifact);
          setJournalDraft(activeJournal.content);
          setJournalTitleDraft(artifact.title);
          setJournalTagsDraft(artifact.tags.join(", "));
        }
        setJournalNotice("Artifact API unavailable; showing legacy daily journals.");
      } else {
        setJournalArtifacts([]);
        setActiveArtifact(undefined);
        setJournalDraft("");
        setJournalTitleDraft("");
        setJournalTagsDraft("");
        setJournalNotice(error instanceof Error ? error.message : "Record artifact API is unavailable.");
      }
    }
  }

  async function openArtifact(summary: JournalArtifactSummary) {
    try {
      if (summary.legacy && summary.date) {
        await openJournal(summary.date);
        return;
      }
      const artifact = await readJournalArtifact(summary.id);
      setActiveArtifact(artifact);
      setJournalDraft(artifact.content);
      setJournalTitleDraft(artifact.title);
      setJournalTagsDraft(artifact.tags.join(", "));
      setJournalNotice("");
    } catch (error) {
      setJournalNotice(error instanceof Error ? error.message : "Unable to open Journal artifact.");
    }
  }

  async function persistJournal() {
    if (!activeArtifact && !activeJournal) {
      return;
    }
    setIsSavingJournal(true);
    try {
      const tags = parseTags(journalTagsDraft);
      if (activeArtifact && !activeArtifact.legacy) {
        const saved = await saveJournalArtifact({
          ...activeArtifact,
          title: journalTitleDraft.trim() || activeArtifact.title,
          tags,
          content: journalDraft,
        });
        const artifacts = await listJournalArtifacts(journalMode);
        setActiveArtifact(saved);
        setJournalArtifacts(artifacts);
        setJournalDraft(saved.content);
        setJournalNotice("Saved Journal artifact.");
      } else if (activeJournal) {
        const saved = await saveJournal(activeJournal.date, withFrontMatter(journalDraft, tags));
        const nextJournals = await listJournals(30);
        const artifact = legacyJournalToArtifact(saved);
        setActiveJournal(saved);
        setActiveArtifact(artifact);
        setJournalDraft(saved.content);
        setJournals(nextJournals);
        setJournalArtifacts(nextJournals.map(legacySummaryToArtifact));
        setJournalNotice("Saved legacy Diary journal.");
      }
      setErrorMessage("");
    } catch (error) {
      setJournalNotice(error instanceof Error ? error.message : "Unable to save Journal.");
    } finally {
      setIsSavingJournal(false);
    }
  }

  async function createRecord() {
    const title = journalTitleDraft.trim() || "New Record";
    setIsSavingJournal(true);
    try {
      const artifact = await createJournalArtifact({
        kind: "record",
        title,
        tags: parseTags(journalTagsDraft),
        content: journalDraft.trim() || `# ${title}\n`,
      });
      const artifacts = await listJournalArtifacts("record");
      setJournalMode("record");
      setJournalArtifacts(artifacts);
      setActiveArtifact(artifact);
      setJournalDraft(artifact.content);
      setJournalTitleDraft(artifact.title);
      setJournalTagsDraft(artifact.tags.join(", "));
      setJournalNotice("Created Record.");
    } catch (error) {
      setJournalNotice(error instanceof Error ? error.message : "Unable to create Record.");
    } finally {
      setIsSavingJournal(false);
    }
  }

  async function submitTodoDraft() {
    if (!todoDraft.title.trim()) {
      return;
    }
    try {
      const payload = {
        title: todoDraft.title.trim(),
        notes: todoDraft.notes.trim() || undefined,
        listId: todoDraft.listId || undefined,
        kind: todoDraft.kind,
        reminderLevel: todoDraft.reminderLevel,
        dueAt: todoDraft.dueAt || undefined,
        reminderAt: todoDraft.reminderAt || undefined,
        source: todoDraft.source.trim() || undefined,
      };
      if (editingTodoId) {
        const existing = todoData.todos.find((todo) => todo.id === editingTodoId);
        if (!existing) {
          throw new Error("Selected Todo no longer exists.");
        }
        await updateTodo({ ...existing, ...payload });
        setTodoNotice("Updated Todo.");
      } else {
        await createTodo(payload);
        setTodoNotice("Created Todo.");
      }
      await reloadTodos();
      resetTodoDraft();
    } catch (error) {
      setTodoNotice(error instanceof Error ? error.message : "Todo API request failed.");
    }
  }

  async function reloadTodos() {
    setTodoData(await listTodoData());
  }

  function editTodo(todo: Todo) {
    setEditingTodoId(todo.id);
    setTodoDraft({
      title: todo.title,
      notes: todo.notes ?? "",
      listId: todo.listId ?? "",
      kind: todo.kind,
      reminderLevel: todo.reminderLevel,
      dueAt: toDateTimeLocal(todo.dueAt),
      reminderAt: toDateTimeLocal(todo.reminderAt),
      source: todo.source ?? "",
    });
  }

  function resetTodoDraft() {
    setEditingTodoId("");
    setTodoDraft({
      title: "",
      notes: "",
      listId: "",
      kind: "task",
      reminderLevel: "normal",
      dueAt: "",
      reminderAt: "",
      source: "",
    });
  }

  async function toggleTodo(todo: Todo) {
    try {
      await completeTodo(todo.id, !todo.completed);
      await reloadTodos();
      setTodoNotice("");
    } catch (error) {
      setTodoNotice(error instanceof Error ? error.message : "Unable to complete Todo.");
    }
  }

  async function removeTodo(id: string) {
    try {
      await deleteTodo(id);
      await reloadTodos();
      if (editingTodoId === id) {
        resetTodoDraft();
      }
      setTodoNotice("Deleted Todo.");
    } catch (error) {
      setTodoNotice(error instanceof Error ? error.message : "Unable to delete Todo.");
    }
  }

  async function saveSettingsDraft() {
    try {
      const saved = await saveSettings(settingsDraft);
      setSettings(saved);
      setSettingsDraft(saved);
      setSettingsNotice("Saved Settings.");
    } catch (error) {
      setSettingsNotice(error instanceof Error ? error.message : "Unable to save Settings.");
    }
  }

  async function addScope() {
    if (!scopeDraftPath.trim()) {
      return;
    }
    try {
      await createProjectScope(scopeDraftPath.trim());
      setProjectScopes(await listProjectScopes());
      setScopeDraftPath("");
      setScopeNotice("Added Project Scope.");
    } catch (error) {
      setScopeNotice(error instanceof Error ? error.message : "Unable to add Project Scope.");
    }
  }

  async function saveScope(scope: ProjectScope) {
    try {
      await updateProjectScope(scope);
      setProjectScopes(await listProjectScopes());
      setScopeNotice("Updated Scope Permission.");
    } catch (error) {
      setScopeNotice(error instanceof Error ? error.message : "Unable to update Project Scope.");
    }
  }

  async function removeScope(id: string) {
    try {
      await deleteProjectScope(id);
      setProjectScopes(await listProjectScopes());
      setScopeNotice("Removed Project Scope.");
    } catch (error) {
      setScopeNotice(error instanceof Error ? error.message : "Unable to remove Project Scope.");
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
      return <TodayView today={todayData} state={appState} daemonStatus={daemonStatus} journals={journals} sessions={sessions} />;
    }
    if (activeView === "todo") {
      return (
        <TodoView
          todoData={todoData}
          todoDraft={todoDraft}
          editingTodoId={editingTodoId}
          filter={todoFilter}
          activeListId={activeTodoListId}
          notice={todoNotice}
          onDraftChange={setTodoDraft}
          onSubmit={submitTodoDraft}
          onCancelEdit={resetTodoDraft}
          onEdit={editTodo}
          onDelete={removeTodo}
          onToggle={toggleTodo}
          onFilterChange={setTodoFilter}
          onListChange={setActiveTodoListId}
        />
      );
    }
    if (activeView === "journal") {
      return (
        <JournalView
          mode={journalMode}
          journals={journals}
          artifacts={journalArtifacts}
          activeJournal={activeJournal}
          activeArtifact={activeArtifact}
          draft={journalDraft}
          titleDraft={journalTitleDraft}
          tagsDraft={journalTagsDraft}
          preview={journalPreview}
          notice={journalNotice}
          isSaving={isSavingJournal}
          onOpen={openJournal}
          onOpenArtifact={openArtifact}
          onModeChange={switchJournalMode}
          onDraftChange={setJournalDraft}
          onTitleChange={setJournalTitleDraft}
          onTagsChange={setJournalTagsDraft}
          onPreviewChange={setJournalPreview}
          onSave={persistJournal}
          onCreateRecord={createRecord}
        />
      );
    }
    if (activeView === "scopes") {
      return (
        <ProjectScopesView
          data={projectScopes}
          draftPath={scopeDraftPath}
          notice={scopeNotice}
          onDraftPathChange={setScopeDraftPath}
          onAdd={addScope}
          onSave={saveScope}
          onDelete={removeScope}
        />
      );
    }
    if (activeView === "settings") {
      return (
        <SettingsView
          settings={settingsDraft}
          appState={appState}
          notice={settingsNotice}
          onChange={setSettingsDraft}
          onSave={saveSettingsDraft}
        />
      );
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
  today,
  state,
  daemonStatus,
  journals,
  sessions,
}: {
  today?: TodayData;
  state?: AppState;
  daemonStatus?: DaemonStatus;
  journals: JournalSummary[];
  sessions: Session[];
}) {
  const date = today?.date ?? state?.today.date ?? new Date().toISOString().slice(0, 10);
  const todos = today?.todos ?? [];
  const artifacts = today?.journalArtifacts ?? journals.map(legacySummaryToArtifact);
  const approvals = today?.pendingApprovals ?? [];
  const recentSessions = today?.recentSessions?.length ? today.recentSessions : sessions;

  return (
    <section className="view-grid today-view">
      <div className="view-intro">
        <div>
          <p className="app-kicker">Today View</p>
          <h3>{formatDate(date)}</h3>
        </div>
        <span className={`journal-state ${state?.today.journal_exists ? "ready" : "pending"}`}>
          {state?.today.journal_exists ? "Diary exists" : "Diary not started"}
        </span>
      </div>

      {today?.error ? <p className="contract-gap wide-panel">{today.error}</p> : null}

      <div className="metric-row">
        <Metric label="Open Todos" value={String(todos.filter((todo) => !todo.completed).length)} />
        <Metric label="Pending Approvals" value={String(approvals.length)} />
        <Metric label="Memory Candidates" value={String(state?.memories.candidates ?? 0)} />
        <Metric label="Delivery Pending" value={String(state?.delivery.pending ?? 0)} />
      </div>

      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Due And Upcoming Todos</h3>
          <span>{todos.length}</span>
        </header>
        <div className="item-list">
          {todos.length ? (
            todos.map((todo) => (
              <article className="list-item" key={todo.id}>
                <strong>{todo.title}</strong>
                <span>{todo.kind} / due {todo.dueAt ? formatCompactDateTime(todo.dueAt) : "not set"} / reminder {todo.reminderLevel}</span>
              </article>
            ))
          ) : (
            <EmptyState title="No todos from Today API" detail="GET /api/today did not return due or upcoming todos." />
          )}
        </div>
      </section>

      <section className="panel">
        <header className="panel-header">
          <h3>Diary And Records</h3>
          <span>{artifacts.length}</span>
        </header>
        <div className="item-list">
          {artifacts.slice(0, 4).map((artifact) => (
            <article className="list-item" key={artifact.id}>
              <strong>{artifact.title}</strong>
              <span>{artifact.kind} {artifact.tags.length ? `/ ${artifact.tags.join(", ")}` : ""}</span>
            </article>
          ))}
          {!artifacts.length ? <EmptyState title="No Journal artifacts" detail="Diary and Record artifacts from /api/today will appear here." /> : null}
        </div>
      </section>

      <section className="panel">
        <header className="panel-header">
          <h3>Recent Sessions</h3>
          <span>{recentSessions.length}</span>
        </header>
        <div className="item-list">
          {recentSessions.slice(0, 4).map((session) => (
            <article className="list-item" key={session.id}>
              <strong>{session.title}</strong>
              <span>{session.summary}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Runtime Status</h3>
          <span>{today?.daemon?.running ?? daemonStatus?.running ? "Daemon running" : "Daemon idle"}</span>
        </header>
        <div className="settings-grid">
          <ReadOnlyField label="Model" value={today?.model?.model ?? "Backend default"} />
          <ReadOnlyField label="Model Status" value={today?.model?.status ?? "Unknown"} />
          <ReadOnlyField label="Daemon Interval" value={`${today?.daemon?.interval_seconds ?? daemonStatus?.interval_seconds ?? 0}s`} />
          <ReadOnlyField label="Companion Nudge" value={today?.companionNudge ?? "Quiet"} />
        </div>
      </section>

      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Pending Approved Actions</h3>
          <span>{approvals.length}</span>
        </header>
        <div className="item-list">
          {approvals.map((approval) => (
            <article className="list-item" key={approval.id}>
              <strong>{approval.title}</strong>
              <span>{approval.summary ?? approval.risk ?? "Waiting for approval"}</span>
            </article>
          ))}
          {!approvals.length ? <EmptyState title="No pending approvals" detail="Actions awaiting approval will appear here when the backend exposes them." /> : null}
        </div>
      </section>
    </section>
  );
}

function TodoView({
  todoData,
  todoDraft,
  editingTodoId,
  filter,
  activeListId,
  notice,
  onDraftChange,
  onSubmit,
  onCancelEdit,
  onEdit,
  onDelete,
  onToggle,
  onFilterChange,
  onListChange,
}: {
  todoData: TodoData;
  todoDraft: {
    title: string;
    notes: string;
    listId: string;
    kind: TodoKind;
    reminderLevel: ReminderLevel;
    dueAt: string;
    reminderAt: string;
    source: string;
  };
  editingTodoId: string;
  filter: "open" | "due" | "done";
  activeListId: string;
  notice: string;
  onDraftChange: (draft: {
    title: string;
    notes: string;
    listId: string;
    kind: TodoKind;
    reminderLevel: ReminderLevel;
    dueAt: string;
    reminderAt: string;
    source: string;
  }) => void;
  onSubmit: () => void;
  onCancelEdit: () => void;
  onEdit: (todo: Todo) => void;
  onDelete: (id: string) => void;
  onToggle: (todo: Todo) => void;
  onFilterChange: (filter: "open" | "due" | "done") => void;
  onListChange: (listId: string) => void;
}) {
  const visibleTodos = todoData.todos.filter((todo) => {
    const matchesList = activeListId === "all" || (activeListId === "none" ? !todo.listId : todo.listId === activeListId);
    const matchesFilter =
      filter === "done" ? todo.completed : filter === "due" ? !todo.completed && Boolean(todo.dueAt) : !todo.completed;
    return matchesList && matchesFilter;
  });
  const grouped = groupTodosByList(visibleTodos, todoData.lists);

  return (
    <section className="view-grid todo-view">
      <div className="view-intro">
        <div>
          <p className="app-kicker">Reliable Commitments</p>
          <h3>Todo List</h3>
        </div>
        <div className="segmented-control" aria-label="Todo filters">
          <button className={filter === "open" ? "is-active" : ""} type="button" onClick={() => onFilterChange("open")}>Open</button>
          <button className={filter === "due" ? "is-active" : ""} type="button" onClick={() => onFilterChange("due")}>Due</button>
          <button className={filter === "done" ? "is-active" : ""} type="button" onClick={() => onFilterChange("done")}>Done</button>
        </div>
      </div>

      <section className="panel form-panel">
        <header className="panel-header">
          <h3>{editingTodoId ? "Edit Todo" : "Create Todo"}</h3>
          <span>{editingTodoId ? editingTodoId : "Manual entry"}</span>
        </header>
        <label className="field">
          <span>Title</span>
          <input
            value={todoDraft.title}
            onChange={(event) => onDraftChange({ ...todoDraft, title: event.target.value })}
            placeholder="Submit assignment, call dentist, prepare notes..."
          />
        </label>
        <label className="field">
          <span>Notes</span>
          <textarea
            value={todoDraft.notes}
            onChange={(event) => onDraftChange({ ...todoDraft, notes: event.target.value })}
            placeholder="Context, checklist, or constraints..."
          />
        </label>
        <label className="field">
          <span>Todo List</span>
          <select
            value={todoDraft.listId}
            onChange={(event) => onDraftChange({ ...todoDraft, listId: event.target.value })}
          >
            <option value="">No list</option>
            {todoData.lists.map((list) => (
              <option value={list.id} key={list.id}>{list.name}</option>
            ))}
          </select>
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
        <label className="field">
          <span>Source</span>
          <input
            value={todoDraft.source}
            onChange={(event) => onDraftChange({ ...todoDraft, source: event.target.value })}
            placeholder="chat/default, journal/2026-06-05, manual..."
          />
        </label>
        <div className="button-row">
          <button className="primary-control" type="button" onClick={onSubmit} disabled={!todoDraft.title.trim()}>
            {editingTodoId ? "Update Todo" : "Save Todo"}
          </button>
          {editingTodoId ? <button className="secondary-control" type="button" onClick={onCancelEdit}>Cancel</button> : null}
        </div>
        {notice ? <p className="contract-gap">{notice}</p> : null}
      </section>

      <section className="panel todo-list-panel">
        <header className="panel-header">
          <h3>Todo Lists</h3>
          <span>{todoData.lists.length}</span>
        </header>
        {todoData.error ? <p className="contract-gap">{todoData.error}</p> : null}
        <div className="segmented-control wrap-control" aria-label="Todo List filter">
          <button className={activeListId === "all" ? "is-active" : ""} type="button" onClick={() => onListChange("all")}>All</button>
          <button className={activeListId === "none" ? "is-active" : ""} type="button" onClick={() => onListChange("none")}>No List</button>
          {todoData.lists.map((list) => (
            <button className={activeListId === list.id ? "is-active" : ""} type="button" key={list.id} onClick={() => onListChange(list.id)}>{list.name}</button>
          ))}
        </div>
      </section>

      <section className="panel wide-panel todo-list-panel">
        <header className="panel-header">
          <h3>Todos</h3>
          <span>{visibleTodos.length}</span>
        </header>
        <div className="item-list">
          {grouped.map((group) => (
            <div className="todo-group" key={group.id}>
              <h4>{group.name}</h4>
              {group.todos.map((todo) => (
                <article className={`list-item todo-item ${todo.completed ? "is-complete" : ""}`} key={todo.id}>
                  <label className="todo-check">
                    <input type="checkbox" checked={todo.completed} onChange={() => onToggle(todo)} />
                    <span>
                      <strong>{todo.title}</strong>
                      <small>
                        {todo.kind} / {todo.reminderLevel}
                        {todo.dueAt ? ` / due ${formatCompactDateTime(todo.dueAt)}` : ""}
                        {todo.reminderAt ? ` / remind ${formatCompactDateTime(todo.reminderAt)}` : ""}
                        {todo.source ? ` / ${todo.source}` : ""}
                      </small>
                    </span>
                  </label>
                  {todo.notes ? <p>{todo.notes}</p> : null}
                  <div className="button-row">
                    <button className="secondary-control" type="button" onClick={() => onEdit(todo)}>Edit</button>
                    <button className="danger-control" type="button" onClick={() => onDelete(todo.id)}>Delete</button>
                  </div>
                </article>
              ))}
            </div>
          ))}
          {!visibleTodos.length ? (
            <EmptyState title="No todos" detail="No Todo items match this filter, or the Todo API returned an error." />
          ) : null}
        </div>
      </section>
    </section>
  );
}

function JournalView({
  mode,
  journals,
  artifacts,
  activeJournal,
  activeArtifact,
  draft,
  titleDraft,
  tagsDraft,
  preview,
  notice,
  isSaving,
  onOpen,
  onOpenArtifact,
  onModeChange,
  onDraftChange,
  onTitleChange,
  onTagsChange,
  onPreviewChange,
  onSave,
  onCreateRecord,
}: {
  mode: JournalArtifactKind;
  journals: JournalSummary[];
  artifacts: JournalArtifactSummary[];
  activeJournal?: JournalDocument;
  activeArtifact?: JournalArtifact;
  draft: string;
  titleDraft: string;
  tagsDraft: string;
  preview: boolean;
  notice: string;
  isSaving: boolean;
  onOpen: (date: string) => void;
  onOpenArtifact: (artifact: JournalArtifactSummary) => void;
  onModeChange: (mode: JournalArtifactKind) => void;
  onDraftChange: (value: string) => void;
  onTitleChange: (value: string) => void;
  onTagsChange: (value: string) => void;
  onPreviewChange: (value: boolean) => void;
  onSave: () => void;
  onCreateRecord: () => void;
}) {
  return (
    <section className="journal-layout">
      <aside className="journal-sidebar">
        <div className="segmented-control">
          <button className={mode === "diary" ? "is-active" : ""} type="button" onClick={() => onModeChange("diary")}>Diary</button>
          <button className={mode === "record" ? "is-active" : ""} type="button" onClick={() => onModeChange("record")}>Record</button>
        </div>
        <div className="item-list">
          {artifacts.map((artifact) => (
            <button
              className={`journal-row ${artifact.id === activeArtifact?.id ? "is-active" : ""}`}
              type="button"
              key={artifact.id}
              onClick={() => onOpenArtifact(artifact)}
            >
              <strong>{artifact.title}</strong>
              <span>{artifact.date ?? artifact.updatedAt ?? artifact.kind}</span>
            </button>
          ))}
          {!artifacts.length && mode === "diary"
            ? journals.map((journal) => (
                <button
                  className={`journal-row ${journal.date === activeJournal?.date ? "is-active" : ""}`}
                  type="button"
                  key={journal.path}
                  onClick={() => onOpen(journal.date)}
                >
                  <strong>{journal.title}</strong>
                  <span>{journal.date}</span>
                </button>
              ))
            : null}
        </div>
        {notice ? <p className="contract-gap">{notice}</p> : null}
      </aside>

      <section className="journal-editor">
        <header className="panel-header">
          <div>
            <p className="app-kicker">{activeArtifact?.legacy ? "Legacy Diary" : mode}</p>
            <h3>{activeArtifact?.title ?? activeJournal?.date ?? "No Journal selected"}</h3>
          </div>
          <div className="button-row">
            <button className="secondary-control" type="button" onClick={() => onPreviewChange(!preview)}>
              {preview ? "Edit" : "Preview"}
            </button>
            <button className="secondary-control" type="button" onClick={onCreateRecord} disabled={isSaving}>
              New Record
            </button>
            <button className="primary-control" type="button" onClick={onSave} disabled={(!activeArtifact && !activeJournal) || isSaving}>
              {isSaving ? "Saving" : "Save"}
            </button>
          </div>
        </header>
        <div className="journal-meta-grid">
          <label className="field">
            <span>Title</span>
            <input value={titleDraft} onChange={(event) => onTitleChange(event.target.value)} />
          </label>
          <label className="field">
            <span>Tags</span>
            <input value={tagsDraft} onChange={(event) => onTagsChange(event.target.value)} placeholder="work, reflection, decision" />
          </label>
        </div>
        {preview ? (
          <div className="markdown-preview">
            {renderMarkdownPreview(draft)}
          </div>
        ) : (
          <textarea
            className="markdown-editor"
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder={mode === "diary" ? "# Today's Diary" : "# Record title"}
          />
        )}
      </section>
    </section>
  );
}

function ProjectScopesView({
  data,
  draftPath,
  notice,
  onDraftPathChange,
  onAdd,
  onSave,
  onDelete,
}: {
  data: ProjectScopeData;
  draftPath: string;
  notice: string;
  onDraftPathChange: (value: string) => void;
  onAdd: () => void;
  onSave: (scope: ProjectScope) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <section className="view-grid">
      <div className="view-intro">
        <div>
          <p className="app-kicker">Scope Permission</p>
          <h3>Project Scopes</h3>
        </div>
      </div>
      <section className="panel wide-panel form-panel">
        <header className="panel-header">
          <h3>Add Directory Scope</h3>
          <span>Authorization boundary</span>
        </header>
        <div className="inline-form">
          <label className="field">
            <span>Directory path</span>
            <input value={draftPath} onChange={(event) => onDraftPathChange(event.target.value)} placeholder="E:\\Code\\Kairos" />
          </label>
          <button className="primary-control" type="button" onClick={onAdd} disabled={!draftPath.trim()}>Add Scope</button>
        </div>
        {notice ? <p className="contract-gap">{notice}</p> : null}
        {data.error ? <p className="contract-gap">{data.error}</p> : null}
      </section>
      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Attached Directories</h3>
          <span>{data.scopes.length}</span>
        </header>
        <div className="item-list">
          {data.scopes.map((scope) => (
            <article className="list-item scope-item" key={scope.id}>
              <div>
                <strong>{scope.name}</strong>
                <span>{scope.path}</span>
              </div>
              <div className="permission-row">
                {(["read", "write", "command"] as const).map((permission) => (
                  <label className="check-pill" key={permission}>
                    <input
                      type="checkbox"
                      checked={scope.permissions[permission]}
                      onChange={(event) =>
                        onSave({ ...scope, permissions: { ...scope.permissions, [permission]: event.target.checked } })
                      }
                    />
                    <span>{permission}</span>
                  </label>
                ))}
                <label className="check-pill">
                  <input
                    type="checkbox"
                    checked={scope.enabled ?? true}
                    onChange={(event) => onSave({ ...scope, enabled: event.target.checked })}
                  />
                  <span>{scope.enabled === false ? "disabled" : "enabled"}</span>
                </label>
              </div>
              <div className="button-row">
                <button className="danger-control" type="button" onClick={() => onDelete(scope.id)}>Delete</button>
              </div>
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

function SettingsView({
  settings,
  appState,
  notice,
  onChange,
  onSave,
}: {
  settings: SettingsSummary & { apiKey?: string };
  appState?: AppState;
  notice: string;
  onChange: (settings: SettingsSummary & { apiKey?: string }) => void;
  onSave: () => void;
}) {
  return (
    <section className="view-grid settings-view">
      <div className="view-intro">
        <div>
          <p className="app-kicker">Local-first Trust</p>
          <h3>Settings</h3>
        </div>
        <button className="primary-control" type="button" onClick={onSave}>Save Settings</button>
      </div>
      <section className="panel">
        <header className="panel-header">
          <h3>DeepSeek Configuration</h3>
          <span>{settings.apiKeyConfigured ? "Secret configured" : "No API key"}</span>
        </header>
        <label className="field">
          <span>Provider</span>
          <input value={settings.provider} onChange={(event) => onChange({ ...settings, provider: event.target.value })} />
        </label>
        <label className="field">
          <span>API Base URL</span>
          <input value={settings.baseUrl} onChange={(event) => onChange({ ...settings, baseUrl: event.target.value })} placeholder="https://api.deepseek.com/v1" />
        </label>
        <label className="field">
          <span>Model</span>
          <input value={settings.model} onChange={(event) => onChange({ ...settings, model: event.target.value })} placeholder="deepseek-chat" />
        </label>
        <label className="field">
          <span>API Key</span>
          <input
            value={settings.apiKey ?? ""}
            onChange={(event) => onChange({ ...settings, apiKey: event.target.value })}
            type="password"
            placeholder={settings.apiKeyConfigured ? "Configured; enter a new key to replace" : "Not configured"}
          />
        </label>
      </section>
      <section className="panel">
        <header className="panel-header">
          <h3>Storage</h3>
          <span>Local</span>
        </header>
        <label className="field">
          <span>Storage Path</span>
          <input
            value={settings.storagePath ?? appState?.doctor.kairos_home ?? ""}
            onChange={(event) => onChange({ ...settings, storagePath: event.target.value })}
          />
        </label>
        <ReadOnlyField label="Journals" value={`${appState?.doctor.journals ?? 0} files`} />
        <ReadOnlyField label="Memory Candidates" value={`${appState?.memories.candidates ?? 0}`} />
      </section>
      <section className="panel wide-panel">
        <header className="panel-header">
          <h3>Configuration Areas</h3>
          <span>Operational policy</span>
        </header>
        <div className="settings-grid">
          <label className="field">
            <span>Notification Policy</span>
            <select value={settings.notifications} onChange={(event) => onChange({ ...settings, notifications: event.target.value })}>
              <option value="pending">Pending</option>
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </select>
          </label>
          <label className="field">
            <span>Notification Detail</span>
            <input value={settings.notificationPolicy ?? ""} onChange={(event) => onChange({ ...settings, notificationPolicy: event.target.value })} placeholder="quiet hours, budget, channels" />
          </label>
          <ReadOnlyField label="Memory Management" value={settings.memoryPath ?? "Memory review entry"} />
          <ReadOnlyField label="Project Scope" value="Open Project Scopes view" />
          <ReadOnlyField label="MCP/Search/Weather" value="Provider controls pending" />
        </div>
        {notice ? <p className="contract-gap">{notice}</p> : null}
        {settings.error ? <p className="contract-gap">{settings.error}</p> : null}
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

function formatCompactDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function toDateTimeLocal(value?: string) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function parseTags(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function frontMatterTags(content: string) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) {
    return [];
  }
  const tagsLine = match[1].split(/\r?\n/).find((line) => line.trim().startsWith("tags:"));
  if (!tagsLine) {
    return [];
  }
  return tagsLine
    .replace(/^tags:\s*/, "")
    .replace(/^\[/, "")
    .replace(/\]$/, "")
    .split(",")
    .map((tag) => tag.trim().replace(/^["']|["']$/g, ""))
    .filter(Boolean);
}

function withFrontMatter(content: string, tags: string[]) {
  const stripped = content.replace(/^---\n[\s\S]*?\n---\n?/, "");
  if (!tags.length) {
    return stripped;
  }
  return `---\ntags: [${tags.join(", ")}]\n---\n\n${stripped}`;
}

function legacyJournalToArtifact(journal: JournalDocument): JournalArtifact {
  const firstHeading = journal.content.split(/\r?\n/).find((line) => line.startsWith("# "));
  return {
    id: `legacy-diary-${journal.date}`,
    kind: "diary",
    title: firstHeading?.replace(/^#\s*/, "") || journal.date,
    date: journal.date,
    path: journal.path,
    preview: journal.content.replace(/^---\n[\s\S]*?\n---\n?/, "").slice(0, 160),
    tags: frontMatterTags(journal.content),
    legacy: true,
    exists: journal.exists,
    content: journal.content,
  };
}

function legacySummaryToArtifact(journal: JournalSummary): JournalArtifactSummary {
  return {
    id: `legacy-diary-${journal.date}`,
    kind: "diary",
    title: journal.title,
    date: journal.date,
    path: journal.path,
    preview: journal.preview,
    tags: [],
    updatedAt: journal.updated_at,
    legacy: true,
  };
}

function groupTodosByList(todos: Todo[], lists: TodoData["lists"]) {
  const byList = new Map(lists.map((list) => [list.id, { id: list.id, name: list.name, todos: [] as Todo[] }]));
  const unlisted = { id: "none", name: "No List", todos: [] as Todo[] };
  for (const todo of todos) {
    const group = todo.listId ? byList.get(todo.listId) : undefined;
    if (group) {
      group.todos.push(todo);
    } else {
      unlisted.todos.push(todo);
    }
  }
  return [...byList.values(), unlisted].filter((group) => group.todos.length);
}

function renderMarkdownPreview(markdown: string) {
  const body = markdown.replace(/^---\n[\s\S]*?\n---\n?/, "");
  const lines = body.split(/\r?\n/);
  return lines.map((line, index) => {
    if (line.startsWith("# ")) {
      return <h1 key={index}>{line.replace(/^#\s*/, "")}</h1>;
    }
    if (line.startsWith("## ")) {
      return <h2 key={index}>{line.replace(/^##\s*/, "")}</h2>;
    }
    if (line.startsWith("- ")) {
      return <p className="bullet-line" key={index}>{line}</p>;
    }
    if (!line.trim()) {
      return <br key={index} />;
    }
    return <p key={index}>{line}</p>;
  });
}

export default App;
