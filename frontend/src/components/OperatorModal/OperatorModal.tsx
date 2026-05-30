import { useState, useEffect, useRef } from 'react';
import type { Operator } from '../../hooks/useOperator';
import './OperatorModal.css';

interface Props {
  initial: Operator | null;
  onSave: (op: Operator) => void;
  onClose?: () => void;
}

export function OperatorModal({ initial, onSave, onClose }: Props) {
  const [operatorName, setOperatorName] = useState(initial?.operatorName ?? '');
  const [callsign, setCallsign] = useState(initial?.callsign ?? '');
  const [location, setLocation] = useState(initial?.location ?? '');
  const firstInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstInputRef.current?.focus();
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!operatorName.trim() || !callsign.trim()) return;
    onSave({ operatorName: operatorName.trim(), callsign: callsign.trim(), location: location.trim() });
  }

  function handleBackdropClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget && onClose) {
      onClose();
    }
  }

  return (
    <div
      className="operator-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="operator-modal-title"
      onClick={handleBackdropClick}
    >
      <div className="operator-modal-panel">
        <h2 id="operator-modal-title" className="operator-modal-title">
          Operator Profile
        </h2>

        <form onSubmit={handleSubmit} noValidate>
          <div className="operator-modal-field">
            <label htmlFor="op-name" className="operator-modal-label">
              Operator Name <span aria-hidden="true">*</span>
            </label>
            <input
              id="op-name"
              ref={firstInputRef}
              type="text"
              className="operator-modal-input"
              value={operatorName}
              onChange={(e) => setOperatorName(e.target.value)}
              required
              autoComplete="name"
              placeholder="e.g. Grandma"
            />
          </div>

          <div className="operator-modal-field">
            <label htmlFor="op-callsign" className="operator-modal-label">
              FCC Call Sign <span aria-hidden="true">*</span>
            </label>
            <input
              id="op-callsign"
              type="text"
              className="operator-modal-input"
              value={callsign}
              onChange={(e) => setCallsign(e.target.value.toUpperCase())}
              required
              autoComplete="off"
              placeholder="e.g. WRFN123"
            />
          </div>

          <div className="operator-modal-field">
            <label htmlFor="op-location" className="operator-modal-label">
              Location
            </label>
            <input
              id="op-location"
              type="text"
              className="operator-modal-input"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              autoComplete="off"
              placeholder="e.g. Home Base"
            />
          </div>

          <button
            type="submit"
            className="operator-modal-save-btn"
            disabled={!operatorName.trim() || !callsign.trim()}
          >
            Save Profile
          </button>
        </form>
      </div>
    </div>
  );
}
