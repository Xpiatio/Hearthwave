import { useEffect, useRef } from 'react';
import './ChatDisplay.css';

export interface ChatEntry {
  id: string;
  timestamp: string; // formatted HH:MM AM/PM
  kind: 'rx' | 'tx' | 'system';
  sender?: string;
  text: string;
  speaker?: string;
  partial?: boolean;
  cluster_label?: string | null;
  onEnrollCluster?: (clusterLabel: string, callsign: string) => void;
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
          className={`chat-entry chat-entry--${entry.kind}${entry.partial ? ' chat-entry--partial' : ''}`}
        >
          <span className="chat-entry-time">{entry.timestamp}</span>
          {' '}
          {entry.kind === 'tx' && (
            <span className="chat-entry-prefix" aria-label="Sent by you">[TX]</span>
          )}
          {entry.kind === 'system' && (
            <span className="chat-entry-prefix" aria-label="System message">[SYS]</span>
          )}
          {entry.speaker && (
            <span className="chat-entry-speaker">[{entry.speaker}]</span>
          )}
          {entry.sender && (
            <span className="chat-entry-sender">[{entry.sender}]:</span>
          )}
          {' '}
          <span className="chat-entry-text">
            {entry.text}
            {entry.partial && <span className="chat-entry-partial-indicator"> …</span>}
          </span>
          {entry.cluster_label && !entry.partial && entry.onEnrollCluster && (
            <button
              className="chat-entry-enroll-btn"
              onClick={() => {
                const callsign = window.prompt(`Assign ${entry.cluster_label} to callsign:`);
                if (callsign && callsign.trim()) {
                  entry.onEnrollCluster!(entry.cluster_label!, callsign.trim().toUpperCase());
                }
              }}
            >
              Identify {entry.cluster_label}
            </button>
          )}
        </div>
      ))}

      <div ref={bottomRef} aria-hidden="true" />
    </main>
  );
}
