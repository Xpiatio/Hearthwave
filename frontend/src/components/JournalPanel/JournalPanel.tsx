import { useState, useEffect } from 'react';
import type { JournalEntry } from '../../types/ws';
import './JournalPanel.css';

interface JournalResultDraft {
  title: string;
  summary: string;
  callsigns_locations: Array<{ callsign: string; location: string }>;
}

interface Props {
  journals: JournalEntry[];
  pendingResult: JournalResultDraft | null;
  generating: boolean;
  journalError: string | null;
  rxTexts: string[];
  rxCallsigns: string[];
  onListJournals: () => void;
  onGenerate: (transcript: string, callsigns: string[]) => void;
  onSave: (title: string, summary: string, callsigns_locations: Array<{ callsign: string; location: string }>, transcript: string) => void;
  onDelete: (file_path: string) => void;
  onDismissResult: () => void;
}

export function JournalPanel({
  journals,
  pendingResult,
  generating,
  journalError,
  rxTexts,
  rxCallsigns,
  onListJournals,
  onGenerate,
  onSave,
  onDelete,
  onDismissResult,
}: Props) {
  const [selected, setSelected] = useState<JournalEntry | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editSummary, setEditSummary] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  useEffect(() => {
    onListJournals();
  }, []);

  useEffect(() => {
    if (pendingResult) {
      setEditTitle(pendingResult.title);
      setEditSummary(pendingResult.summary);
    }
  }, [pendingResult]);

  function handleGenerate() {
    const transcript = rxTexts.join('\n');
    onGenerate(transcript, rxCallsigns);
  }

  function handleSave() {
    if (!pendingResult) return;
    onSave(
      editTitle,
      editSummary,
      pendingResult.callsigns_locations,
      rxTexts.join('\n'),
    );
    onDismissResult();
  }

  function handleDelete(file: string) {
    if (confirmDelete === file) {
      onDelete(file);
      setConfirmDelete(null);
      if (selected?._file === file) setSelected(null);
    } else {
      setConfirmDelete(file);
    }
  }

  const transcript = rxTexts.join('\n');
  const hasSession = transcript.trim().length > 0;

  return (
    <div className="journal-panel">
      <div className="journal-left">
        <div className="journal-left-header">JOURNALS</div>
        {journals.length === 0 ? (
          <p className="journal-empty">No saved journals.</p>
        ) : (
          <ul className="journal-list">
            {journals.map((j) => (
              <li
                key={j._file}
                className={`journal-list-item ${selected?._file === j._file ? 'journal-list-item--active' : ''}`}
                onClick={() => { setSelected(j); onDismissResult(); }}
              >
                <span className="journal-item-date">{j.exported_at.slice(0, 10)}</span>
                <span className="journal-item-title">{j.title || '(untitled)'}</span>
                <button
                  className={`journal-delete-btn ${confirmDelete === j._file ? 'journal-delete-btn--confirm' : ''}`}
                  onClick={(e) => { e.stopPropagation(); handleDelete(j._file); }}
                  title={confirmDelete === j._file ? 'Click again to confirm delete' : 'Delete entry'}
                >
                  {confirmDelete === j._file ? 'CONFIRM' : '✕'}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="journal-generate-area">
          {journalError && <p className="journal-error">{journalError}</p>}
          <button
            className="journal-generate-btn"
            onClick={handleGenerate}
            disabled={generating || !hasSession}
            title={!hasSession ? 'No received messages to summarise' : ''}
          >
            {generating ? 'GENERATING...' : 'GENERATE FROM SESSION'}
          </button>
        </div>
      </div>

      <div className="journal-right">
        {pendingResult ? (
          <div className="journal-draft">
            <div className="journal-draft-header">AI DRAFT — REVIEW AND SAVE</div>
            <label className="journal-field-label">Title</label>
            <input
              className="journal-title-input"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
            />
            <label className="journal-field-label">Summary</label>
            <textarea
              className="journal-summary-textarea"
              value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)}
              rows={8}
            />
            {pendingResult.callsigns_locations.length > 0 && (
              <>
                <label className="journal-field-label">Callsigns</label>
                <table className="journal-callsigns-table">
                  <thead><tr><th>Callsign</th><th>Location</th></tr></thead>
                  <tbody>
                    {pendingResult.callsigns_locations.map((cl) => (
                      <tr key={cl.callsign}>
                        <td>{cl.callsign}</td>
                        <td>{cl.location}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
            <div className="journal-draft-actions">
              <button className="journal-save-btn" onClick={handleSave} disabled={!editTitle.trim()}>
                SAVE JOURNAL
              </button>
              <button className="journal-discard-btn" onClick={onDismissResult}>
                DISCARD
              </button>
            </div>
          </div>
        ) : selected ? (
          <div className="journal-detail">
            <div className="journal-detail-date">{selected.exported_at}</div>
            <h2 className="journal-detail-title">{selected.title || '(untitled)'}</h2>
            {selected.callsigns_locations.length > 0 && (
              <table className="journal-callsigns-table">
                <thead><tr><th>Callsign</th><th>Location</th></tr></thead>
                <tbody>
                  {selected.callsigns_locations.map((cl) => (
                    <tr key={cl.callsign}>
                      <td>{cl.callsign}</td>
                      <td>{cl.location}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="journal-detail-summary">{selected.summary}</p>
            {selected.transcript && (
              <details className="journal-transcript">
                <summary>Session transcript</summary>
                <pre>{selected.transcript}</pre>
              </details>
            )}
          </div>
        ) : (
          <p className="journal-placeholder">Select a journal or generate a new one.</p>
        )}
      </div>
    </div>
  );
}
