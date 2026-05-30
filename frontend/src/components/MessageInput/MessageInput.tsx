import { useState, useRef } from 'react';
import type { Contact } from '../../types/ws';
import './MessageInput.css';

interface Props {
  transmitting: boolean;
  contacts: Contact[];
  onSend: (text: string, targetCall: string, targetName: string) => void;
}

export function MessageInput({ transmitting, contacts, onSend }: Props) {
  const [draft, setDraft] = useState('');
  const [targetCallsign, setTargetCallsign] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const text = draft.trim();
    if (!text || transmitting) return;
    const contact = contacts.find((c) => c.callsign === targetCallsign);
    onSend(text, contact ? contact.callsign : 'ALL', contact ? contact.name : '');
    setDraft('');
    textareaRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && (e.ctrlKey || e.metaKey || e.nativeEvent.isComposing === false)) {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        handleSend();
      }
    }
  }

  const selectedContact = contacts.find((c) => c.callsign === targetCallsign);

  return (
    <div className="message-input-wrapper">
      {transmitting && (
        <div
          className="transmitting-banner"
          role="alert"
          aria-live="assertive"
        >
          <span aria-hidden="true">⚠️</span>
          <span> SENDING MESSAGE NOW... PLEASE WAIT</span>
        </div>
      )}

      <div className="message-input-area">
        <div className="message-target-row">
          <label htmlFor="message-target-select" className="message-target-label">
            To:
          </label>
          <select
            id="message-target-select"
            className="message-target-select"
            value={targetCallsign}
            onChange={(e) => setTargetCallsign(e.target.value)}
            disabled={transmitting}
          >
            <option value="">ALL — Broadcast</option>
            {contacts.map((c) => (
              <option key={c.callsign} value={c.callsign}>
                {c.callsign}{c.name ? ` — ${c.name}` : ''}
              </option>
            ))}
          </select>
        </div>

        {selectedContact && (
          <div className="message-target-badge" aria-live="polite">
            Calling {selectedContact.callsign}
            {selectedContact.name ? ` (${selectedContact.name})` : ''}
            {selectedContact.location ? ` · ${selectedContact.location}` : ''}
          </div>
        )}

        <label htmlFor="message-textarea" className="message-input-label">
          Type Your Message Below:
        </label>
        <textarea
          id="message-textarea"
          ref={textareaRef}
          className="message-input-textarea"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={transmitting}
          aria-disabled={transmitting}
          placeholder={transmitting ? '' : 'Enter your message here...'}
          aria-label="Message text — press Ctrl+Enter or use the Send button to transmit"
        />
      </div>

      <button
        className="message-send-btn"
        onClick={handleSend}
        disabled={transmitting || !draft.trim()}
        aria-label="Press to send message over radio"
      >
        PRESS TO SEND MESSAGE
      </button>
    </div>
  );
}
