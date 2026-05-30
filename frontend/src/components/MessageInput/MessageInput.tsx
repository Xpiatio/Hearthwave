import { useState, useRef } from 'react';
import './MessageInput.css';

interface Props {
  transmitting: boolean;
  onSend: (text: string) => void;
}

export function MessageInput({ transmitting, onSend }: Props) {
  const [draft, setDraft] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const text = draft.trim();
    if (!text || transmitting) return;
    onSend(text);
    setDraft('');
    textareaRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Ctrl+Enter or Cmd+Enter sends on desktop; plain Enter on touchscreen
    // Use shift+Enter for newline on physical keyboards
    if (e.key === 'Enter' && !e.shiftKey && (e.ctrlKey || e.metaKey || e.nativeEvent.isComposing === false)) {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        handleSend();
      }
    }
  }

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
