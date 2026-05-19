import type { Session } from "../types";

type Props = {
  sessions: Session[];
  activeSessionId: string;
  query: string;
  onQueryChange: (value: string) => void;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
};

export function SessionSidebar({
  sessions,
  activeSessionId,
  query,
  onQueryChange,
  onSelectSession,
  onNewSession,
}: Props) {
  return (
    <aside className="session-sidebar" aria-label="Conversation list">
      <div className="sidebar-header">
        <div>
          <p className="app-kicker">Kairos</p>
          <h1>Agent Console</h1>
        </div>
        <button className="icon-button" type="button" aria-label="New session" onClick={onNewSession}>
          +
        </button>
      </div>

      <label className="search-box">
        <span className="visually-hidden">Search sessions</span>
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search sessions"
          type="search"
        />
      </label>

      <div className="session-list" role="listbox" aria-label="Sessions">
        {sessions.map((session) => (
          <button
            className={`session-row ${session.id === activeSessionId ? "is-active" : ""}`}
            type="button"
            key={session.id}
            onClick={() => onSelectSession(session.id)}
            role="option"
            aria-selected={session.id === activeSessionId}
          >
            <span className={`status-dot status-${session.status}`} aria-hidden="true" />
            <span className="session-copy">
              <span className="session-title">{session.title}</span>
              <span className="session-summary">{session.summary}</span>
            </span>
            <span className="session-meta">
              <span>{session.updatedAt}</span>
              {session.unreadCount ? <strong>{session.unreadCount}</strong> : null}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
