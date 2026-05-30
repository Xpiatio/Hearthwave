import { useState } from 'react';
import './TopBar.css';

interface Props {
  stationStatus: string;
  connected: boolean;
  onChangeOperator: () => void;
}

export function TopBar({ stationStatus, connected, onChangeOperator }: Props) {
  const [voiceOn, setVoiceOn] = useState(false);

  function handleVoiceToggle() {
    setVoiceOn((prev) => !prev);
  }

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="topbar-btn"
          onClick={onChangeOperator}
          aria-label="Change operator profile"
        >
          CHANGE OPERATOR
        </button>
      </div>

      <div className="topbar-center" aria-live="polite" aria-atomic="true">
        <span className="topbar-status-label">STATION STATUS:</span>
        <span className={`topbar-status-value ${connected ? 'topbar-status--ready' : 'topbar-status--offline'}`}>
          {connected ? stationStatus : 'OFFLINE'}
        </span>
      </div>

      <div className="topbar-right">
        <button
          className={`topbar-btn topbar-voice-btn ${voiceOn ? 'topbar-voice-btn--on' : ''}`}
          onClick={handleVoiceToggle}
          aria-label={voiceOn ? 'Voice on — press to turn off' : 'Voice off — press to turn on'}
          aria-pressed={voiceOn}
        >
          {voiceOn ? 'VOICE ON' : 'VOICE OFF'}
        </button>
      </div>
    </header>
  );
}
