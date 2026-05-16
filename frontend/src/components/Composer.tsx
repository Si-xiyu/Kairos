import { KeyboardEvent } from "react";

type Props = {
  value: string;
  isGenerating: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
};

export function Composer({ value, isGenerating, onChange, onSend, onStop }: Props) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  }

  return (
    <footer className="composer-shell" aria-label="Message composer">
      <div className="composer">
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Kairos to inspect, plan, code, remember, or reflect..."
          rows={3}
        />
        <div className="composer-actions">
          <span>Enter to send · Shift+Enter for newline</span>
          <div>
            <button className="secondary-control" type="button" onClick={onStop} disabled={!isGenerating}>
              Stop
            </button>
            <button className="primary-control" type="button" onClick={onSend} disabled={!value.trim()}>
              Send
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
