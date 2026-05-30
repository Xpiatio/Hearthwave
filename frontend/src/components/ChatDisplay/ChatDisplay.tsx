import { useEffect, useRef } from 'react';
import './ChatDisplay.css';

export interface ChatEntry {
  id: string;
  timestamp: string; // formatted HH:MM AM/PM
  kind: 'rx' | 'tx' | 'system';
  sender?: string;
  text: string;
}

interface Props {
  entries: ChatEntry[];
}

export function ChatDisplay({ entries }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  return (
    <main className="chat-display" aria-label="Message history" aria-live="polite" aria-relevant="additions">
      {entries.length === 0 && (
        <p className="chat-display-empty">No messages yet. Waiting for radio traffic...</p>
      )}

      {entries.map((entry) => (
        <div
          key={entry.id}
          className={`chat-entry chat-entry--${entry.kind}`}
        >
          <span className="chat-entry-time">{entry.timestamp}</span>
          {' '}
          {entry.kind === 'tx' && (
            <span className="chat-entry-prefix" aria-label="Sent by you">[TX]</span>
          )}
          {entry.kind === 'system' && (
            <span className="chat-entry-prefix" aria-label="System message">[SYS]</span>
          )}
          {entry.sender && (
            <span className="chat-entry-sender">[{entry.sender}]:</span>
          )}
          {' '}
          <span className="chat-entry-text">{entry.text}</span>
        </div>
      ))}

      <div ref={bottomRef} aria-hidden="true" />
    </main>
  );
}
