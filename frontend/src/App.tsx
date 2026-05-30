import { useState, useCallback, useRef } from 'react';
import { useOperator } from './hooks/useOperator';
import { useWebSocket } from './hooks/useWebSocket';
import type {
  WsMessage,
  StatusMsg,
  TxMessagePayload,
  Contact,
  AttendanceStation,
  JournalEntry,
} from './types/ws';
import { OperatorModal } from './components/OperatorModal/OperatorModal';
import { TopBar } from './components/TopBar/TopBar';
import { ChatDisplay } from './components/ChatDisplay/ChatDisplay';
import type { ChatEntry } from './components/ChatDisplay/ChatDisplay';
import { StatusRow } from './components/StatusRow/StatusRow';
import { MessageInput } from './components/MessageInput/MessageInput';
import type { MessageInputHandle } from './components/MessageInput/MessageInput';
import { AttendancePanel } from './components/AttendancePanel/AttendancePanel';
import { JournalPanel } from './components/JournalPanel/JournalPanel';
import { Spectrogram } from './components/Spectrogram/Spectrogram';
import type { SpectrogramHandle } from './components/Spectrogram/Spectrogram';
import { QuickMessages } from './components/QuickMessages/QuickMessages';
import './App.css';

let entryCounter = 0;
function nextId() {
  return `msg-${++entryCounter}`;
}

function formatTime(isoOrNow?: string): string {
  const d = isoOrNow ? new Date(isoOrNow) : new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function speakerLabel(callsign: string | null, name: string | null, cluster: string | null): string | undefined {
  if (callsign && name) return `${callsign} — ${name}`;
  if (callsign) return callsign;
  if (cluster) return cluster;
  return undefined;
}

interface JournalResultDraft {
  title: string;
  summary: string;
  callsigns_locations: Array<{ callsign: string; location: string }>;
}

export default function App() {
  const { operator, setOperator } = useOperator();
  const [showModal, setShowModal] = useState(operator === null);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [radioStatus, setRadioStatus] = useState<StatusMsg | null>(null);
  const [transmitting, setTransmitting] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const inProgressRef = useRef<Map<string, string>>(new Map());
  const sendRef = useRef<(p: unknown) => void>(() => {});
  const messageInputRef = useRef<MessageInputHandle>(null);
  const spectroRef = useRef<SpectrogramHandle>(null);

  // Panel visibility
  const [showAttendance, setShowAttendance] = useState(false);
  const [showJournal, setShowJournal] = useState(false);

  // Attendance
  const [attendanceStations, setAttendanceStations] = useState<AttendanceStation[]>([]);

  // Journals
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [journalResult, setJournalResult] = useState<JournalResultDraft | null>(null);
  const [journalGenerating, setJournalGenerating] = useState(false);
  const [journalError, setJournalError] = useState<string | null>(null);

  const handleWsMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'rx_message': {
        const uid = msg.utterance_id;
        if (msg.partial) {
          setMessages((prev) => {
            const existingId = inProgressRef.current.get(uid);
            if (existingId) {
              return prev.map((e) =>
                e.id === existingId ? { ...e, text: msg.text, partial: true } : e
              );
            }
            const id = nextId();
            inProgressRef.current.set(uid, id);
            return [
              ...prev,
              {
                id,
                timestamp: formatTime(msg.ts),
                kind: 'rx',
                sender: msg.from || msg.callsign || undefined,
                text: msg.text,
                partial: true,
              },
            ];
          });
        } else {
          const speaker = speakerLabel(msg.speaker_callsign, msg.speaker_name, msg.cluster_label);
          setMessages((prev) => {
            const existingId = inProgressRef.current.get(uid);
            inProgressRef.current.delete(uid);
            if (existingId) {
              return prev.map((e) =>
                e.id === existingId
                  ? {
                      ...e,
                      text: msg.text,
                      partial: false,
                      speaker,
                      cluster_label: msg.cluster_label,
                      onEnrollCluster: msg.cluster_label
                        ? (cl: string, cs: string) => sendRef.current({ type: 'enroll_speaker', callsign: cs, cluster_label: cl })
                        : undefined,
                    }
                  : e
              );
            }
            return [
              ...prev,
              {
                id: nextId(),
                timestamp: formatTime(msg.ts),
                kind: 'rx',
                sender: msg.from || msg.callsign || undefined,
                text: msg.text,
                speaker,
                cluster_label: msg.cluster_label,
                onEnrollCluster: msg.cluster_label
                  ? (cl: string, cs: string) => sendRef.current({ type: 'enroll_speaker', callsign: cs, cluster_label: cl })
                  : undefined,
              },
            ];
          });
        }
        break;
      }

      case 'status':
        setRadioStatus(msg);
        break;

      case 'tx_status':
        setTransmitting(msg.status === 'transmitting');
        break;

      case 'system_msg':
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            timestamp: formatTime(),
            kind: 'system',
            text: msg.text,
          },
        ]);
        break;

      case 'contacts':
        setContacts(msg.contacts);
        break;

      case 'speaker_enrolled':
        console.log(`Speaker enrolled: ${msg.callsign} (${msg.name}), ${msg.sample_count} samples`);
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            timestamp: formatTime(),
            kind: 'system',
            text: `${msg.callsign} enrolled as a known speaker`,
          },
        ]);
        break;

      case 'speaker_reset':
        console.log(`Speaker reset: ${msg.callsign}`);
        break;

      case 'session_attendance':
        setAttendanceStations(msg.stations);
        break;

      case 'journals':
        setJournals(msg.journals);
        break;

      case 'journal_result':
        setJournalResult({
          title: msg.title,
          summary: msg.summary,
          callsigns_locations: msg.callsigns_locations,
        });
        setJournalGenerating(false);
        setJournalError(null);
        break;

      case 'journal_error':
        setJournalError(msg.detail);
        setJournalGenerating(false);
        break;

      case 'journal_saved':
        // Refresh journal list after save
        sendRef.current({ type: 'list_journals' });
        break;

      case 'journal_deleted':
        setJournals((prev) => prev.filter((j) => j._file !== msg.file_path));
        break;

      case 'spectrogram_row':
        spectroRef.current?.pushRow(msg.row);
        break;
    }
  }, []);

  const { send, connected } = useWebSocket({ onMessage: handleWsMessage });
  sendRef.current = send;

  function handleSend(text: string, targetCall: string, targetName: string) {
    if (!operator) {
      setShowModal(true);
      return;
    }
    const payload: TxMessagePayload = {
      type: 'tx_message',
      text,
      operator: operator.operatorName,
      callsign: operator.callsign,
      target_call: targetCall,
      target_name: targetName,
    };
    send(payload);
    setMessages((prev) => [
      ...prev,
      {
        id: nextId(),
        timestamp: formatTime(),
        kind: 'tx',
        sender: operator.callsign,
        text,
      },
    ]);
  }

  // Derived: RX texts and callsigns from current chat for journal generation
  const rxMessages = messages.filter((m) => m.kind === 'rx' && !m.partial);
  const rxTexts = rxMessages.map((m) => (m.sender ? `[${m.sender}] ${m.text}` : m.text));
  const rxCallsigns = [...new Set(
    rxMessages.map((m) => m.sender).filter(Boolean) as string[]
  )];

  const stationStatus = connected ? 'READY' : 'OFFLINE';

  return (
    <div className="app-shell">
      {showModal && (
        <OperatorModal
          initial={operator}
          onSave={(op) => {
            setOperator(op);
            setShowModal(false);
          }}
          onClose={operator ? () => setShowModal(false) : undefined}
        />
      )}

      <TopBar
        stationStatus={stationStatus}
        connected={connected}
        onChangeOperator={() => setShowModal(true)}
        showAttendance={showAttendance}
        onToggleAttendance={() => setShowAttendance((v) => !v)}
        showJournal={showJournal}
        onToggleJournal={() => {
          setShowJournal((v) => !v);
        }}
      />

      {showAttendance && (
        <AttendancePanel
          stations={attendanceStations}
          onClear={() => send({ type: 'clear_attendance' })}
        />
      )}

      {showJournal && (
        <JournalPanel
          journals={journals}
          pendingResult={journalResult}
          generating={journalGenerating}
          journalError={journalError}
          rxTexts={rxTexts}
          rxCallsigns={rxCallsigns}
          onListJournals={() => send({ type: 'list_journals' })}
          onGenerate={(transcript, callsigns) => {
            setJournalGenerating(true);
            setJournalError(null);
            setJournalResult(null);
            send({ type: 'generate_journal', transcript, callsigns });
          }}
          onSave={(title, summary, callsigns_locations, transcript) => {
            send({ type: 'save_journal', title, summary, callsigns_locations, transcript });
          }}
          onDelete={(file_path) => send({ type: 'delete_journal', file_path })}
          onDismissResult={() => setJournalResult(null)}
        />
      )}

      <ChatDisplay entries={messages} />

      <Spectrogram ref={spectroRef} />

      <StatusRow status={radioStatus} />

      <QuickMessages
        operatorName={operator?.operatorName ?? ''}
        onSelect={(text) => messageInputRef.current?.setText(text)}
      />

      <MessageInput
        ref={messageInputRef}
        transmitting={transmitting}
        contacts={contacts}
        myCallsign={operator?.callsign ?? ''}
        onSend={handleSend}
      />
    </div>
  );
}
