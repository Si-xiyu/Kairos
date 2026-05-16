import type { Message, MessageBlock, Session } from "../types";

type Props = {
  session?: Session;
  messages: Message[];
  isGenerating: boolean;
};

function renderBlock(block: MessageBlock, index: number) {
  if (block.kind === "code") {
    return (
      <figure className="code-block" key={index}>
        <figcaption>{block.language}</figcaption>
        <pre>
          <code>{block.content}</code>
        </pre>
      </figure>
    );
  }

  const lines = block.content.split("\n");
  return (
    <div className={block.kind === "markdown" ? "markdown-block" : "text-block"} key={index}>
      {lines.map((line, lineIndex) => {
        if (!line.trim()) {
          return <br key={lineIndex} />;
        }
        if (line.trim().startsWith("- ")) {
          return <p key={lineIndex} className="bullet-line">{line.trim()}</p>;
        }
        return <p key={lineIndex}>{line}</p>;
      })}
    </div>
  );
}

export function MessageStream({ session, messages, isGenerating }: Props) {
  return (
    <main className="conversation" aria-label="Conversation">
      <header className="conversation-header">
        <div>
          <p className="app-kicker">Local-first session</p>
          <h2>{session?.title ?? "Untitled session"}</h2>
        </div>
        <div className="runtime-pill">
          <span className={isGenerating ? "pulse-dot" : "quiet-dot"} aria-hidden="true" />
          {isGenerating ? "Generating" : "Ready"}
        </div>
      </header>

      <section className="message-scroll" aria-live="polite">
        {messages.map((message) => (
          <article className={`message message-${message.role}`} key={message.id}>
            <div className="message-avatar" aria-hidden="true">
              {message.role === "user" ? "Y" : "K"}
            </div>
            <div className="message-body">
              <div className="message-meta">
                <strong>{message.author}</strong>
                <span>{message.createdAt}</span>
                {message.status === "streaming" ? <em>streaming</em> : null}
              </div>
              <div className="message-content">{message.blocks.map(renderBlock)}</div>
            </div>
          </article>
        ))}

        {isGenerating ? (
          <article className="message message-assistant stream-placeholder">
            <div className="message-avatar" aria-hidden="true">K</div>
            <div className="message-body">
              <div className="message-meta">
                <strong>Kairos</strong>
                <em>streaming</em>
              </div>
              <div className="typing-line">
                <span />
                <span />
                <span />
              </div>
            </div>
          </article>
        ) : null}
      </section>
    </main>
  );
}
