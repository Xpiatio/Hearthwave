import { useState, useEffect } from 'react';
import './QuickMessages.css';

const STORAGE_KEY = 'radio_tty_quick_messages';
const DEFAULTS = ['Standing by', 'QSL', 'Copy that', 'QSY to channel {N}', 'Good signal'];

function load(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed as string[];
    }
  } catch {
    // ignore
  }
  return DEFAULTS.slice();
}

function save(phrases: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(phrases));
}

interface Props {
  operatorName: string;
  onSelect: (text: string) => void;
}

export function QuickMessages({ operatorName, onSelect }: Props) {
  const [phrases, setPhrases] = useState<string[]>(load);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  useEffect(() => {
    save(phrases);
  }, [phrases]);

  function handleSelect(phrase: string) {
    const text = phrase.replace(/{Name}/gi, operatorName || 'Operator');
    onSelect(text);
  }

  function handleAdd() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    setPhrases((prev) => [...prev, trimmed]);
    setDraft('');
  }

  function handleRemove(idx: number) {
    setPhrases((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleMoveUp(idx: number) {
    if (idx === 0) return;
    setPhrases((prev) => {
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
  }

  function handleMoveDown(idx: number) {
    setPhrases((prev) => {
      if (idx >= prev.length - 1) return prev;
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next;
    });
  }

  return (
    <div className="quick-messages">
      {editing ? (
        <div className="quick-messages-editor">
          <div className="quick-editor-header">
            <span className="quick-editor-title">QUICK MESSAGES</span>
            <button className="quick-editor-done" onClick={() => setEditing(false)}>DONE</button>
          </div>
          <ul className="quick-editor-list">
            {phrases.map((p, i) => (
              <li key={i} className="quick-editor-item">
                <span className="quick-editor-text">{p}</span>
                <div className="quick-editor-controls">
                  <button onClick={() => handleMoveUp(i)} disabled={i === 0} aria-label="Move up">↑</button>
                  <button onClick={() => handleMoveDown(i)} disabled={i === phrases.length - 1} aria-label="Move down">↓</button>
                  <button onClick={() => handleRemove(i)} aria-label="Remove">✕</button>
                </div>
              </li>
            ))}
          </ul>
          <div className="quick-editor-add">
            <input
              className="quick-editor-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              placeholder="New phrase… use {Name} for operator name"
            />
            <button className="quick-editor-add-btn" onClick={handleAdd} disabled={!draft.trim()}>ADD</button>
          </div>
        </div>
      ) : (
        <div className="quick-messages-bar">
          <div className="quick-buttons-scroll">
            {phrases.map((p, i) => (
              <button
                key={i}
                className="quick-phrase-btn"
                onClick={() => handleSelect(p)}
                title={p}
              >
                {p.replace(/{Name}/gi, operatorName || 'Operator')}
              </button>
            ))}
          </div>
          <button
            className="quick-settings-btn"
            onClick={() => setEditing(true)}
            aria-label="Edit quick messages"
            title="Edit quick messages"
          >
            ⚙
          </button>
        </div>
      )}
    </div>
  );
}
