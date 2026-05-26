import { useEffect, useState } from "react";
import type { AgentEvent, AgentEventKind } from "../types";

type Props = {
  events: AgentEvent[];
  backendStatus: "online" | "offline";
};

const labels: Record<AgentEventKind, string> = {
  tool_call: "Tool Call",
  tool_result: "Tool Result",
  runtime: "Runtime",
  memory: "Memory",
};

export function AgentInspector({ events, backendStatus }: Props) {
  const [openIds, setOpenIds] = useState<Set<string>>(() => new Set(events.slice(0, 2).map((event) => event.id)));

  useEffect(() => {
    setOpenIds(new Set(events.slice(0, 2).map((event) => event.id)));
  }, [events]);

  function toggle(id: string) {
    setOpenIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <aside className="agent-inspector" aria-label="Agent inspector">
      <div className="inspector-header">
        <div>
          <p className="app-kicker">Agent Harness</p>
          <h2>Inspector</h2>
        </div>
        <span>{events.length}</span>
      </div>

      <div className="runtime-strip">
        <div>
          <span>Runtime</span>
          <strong>{backendStatus === "online" ? "FastAPI" : "Offline"}</strong>
        </div>
        <div>
          <span>Transport</span>
          <strong>REST</strong>
        </div>
      </div>

      <div className="event-list">
        {events.map((event) => {
          const isOpen = openIds.has(event.id);
          return (
            <section className={`event-card event-${event.status}`} key={event.id}>
              <button className="event-toggle" type="button" onClick={() => toggle(event.id)} aria-expanded={isOpen}>
                <span className="event-kind">{labels[event.kind]}</span>
                <span className="event-title">{event.title}</span>
                <span className="event-time">{event.timestamp}</span>
              </button>
              <p>{event.summary}</p>
              {isOpen ? <pre>{event.details}</pre> : null}
            </section>
          );
        })}
      </div>
    </aside>
  );
}
