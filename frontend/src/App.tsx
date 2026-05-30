import { useState, useCallback, useRef, useMemo } from 'react';
import { ThemeProvider, CssBaseline, Box } from '@mui/material';
import { makeTheme } from './theme';
import { useOperator } from './hooks/useOperator';
import { useWebSocket } from './hooks/useWebSocket';
import type {
  WsMessage,
  StatusMsg,
  TxMessagePayload,
  Contact,
  AttendanceStation,
  JournalEntry,
  FccLookupResultMsg,
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
import { ContactsDialog } from './components/ContactsDialog/ContactsDialog';
import { PendingStationsBar } from './components/PendingStationsBar/PendingStationsBar';
import { ConfigPanel } from './components/ConfigPanel/ConfigPanel';
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

interface PendingStation {
  callsign: string;
  name: string;
  location: string;
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
  const operatorRef = useRef(operator);
  operatorRef.current = operator;

  // Panel visibility
  const [showAttendance, setShowAttendance] = useState(false);
  const [showJournal, setShowJournal] = useState(false);
  const [showContacts, setShowContacts] = useState(false);
  const [showConfig, setShowConfig] = useState(false);

  // Theme
  const [darkMode, setDarkMode] = useState(
    () => localStorage.getItem('radio_tty_dark_mode') === 'true'
  );
  const [touchMode, setTouchMode] = useState(
    () => localStorage.getItem('radio_tty_touch_mode') === 'true'
  );
  const theme = useMemo(() => makeTheme(darkMode, touchMode), [darkMode, touchMode]);

  function handleToggleDark() {
    setDarkMode((v) => {
      localStorage.setItem('radio_tty_dark_mode', String(!v));
      return !v;
    });
  }

  function handleToggleTouch() {
    setTouchMode((v) => {
      localStorage.setItem('radio_tty_touch_mode', String(!v));
      return !v;
    });
  }

  // Attendance
  const [attendanceStations, setAttendanceStations] = useState<AttendanceStation[]>([]);

  // Journals
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [journalResult, setJournalResult] = useState<JournalResultDraft | null>(null);
  const [journalGenerating, setJournalGenerating] = useState(false);
  const [journalError, setJournalError] = useState<string | null>(null);

  // FCC / Callsigns
  const [pendingStations, setPendingStations] = useState<PendingStation[]>([]);
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [fccLookupResult, setFccLookupResult] = useState<FccLookupResultMsg | null>(null);
  const [verifyAllComplete, setVerifyAllComplete] = useState(false);
  const [pendingPrefilledCallsign, setPendingPrefilledCallsign] = useState<string | undefined>();

  // Config (synced from server status message)
  const [listenOnly, setListenOnly] = useState(false);
  const [serviceMode, setServiceMode] = useState('GMRS');
  const [filterProfanity, setFilterProfanity] = useState(true);
  const [fuzzyCallsign, setFuzzyCallsign] = useState(false);
  const [systemMonitorSink, setSystemMonitorSinkLocal] = useState('');
  const [spectroColormap, setSpectroColormap] = useState<'viridis' | 'grayscale'>('viridis');
  const [spectroFreqRange, setSpectroFreqRange] = useState<'voice' | 'full'>('full');
  const [spectroTimeWindowS, setSpectroTimeWindowS] = useState(30);

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
        if (msg.listen_only !== undefined) setListenOnly(msg.listen_only);
        if (msg.service_mode !== undefined) setServiceMode(msg.service_mode);
        if (msg.filter_profanity !== undefined) setFilterProfanity(msg.filter_profanity);
        if (msg.fuzzy_callsign !== undefined) setFuzzyCallsign(msg.fuzzy_callsign);
        if (msg.spectro_colormap === 'viridis' || msg.spectro_colormap === 'grayscale')
          setSpectroColormap(msg.spectro_colormap);
        if (msg.spectro_freq_range === 'voice' || msg.spectro_freq_range === 'full')
          setSpectroFreqRange(msg.spectro_freq_range);
        if (msg.spectro_time_window_s !== undefined) setSpectroTimeWindowS(msg.spectro_time_window_s);
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
        break;

      case 'prompt_token': {
        const tokens = msg.tokens;
        let resolvedText = msg.original_text;
        let cancelled = false;
        for (const token of tokens) {
          const val = window.prompt(`Enter value for {${token}}:`);
          if (val === null) { cancelled = true; break; }
          resolvedText = resolvedText.replaceAll(`{${token}}`, val);
        }
        if (!cancelled) {
          sendRef.current({
            type: 'tx_message',
            text: resolvedText,
            operator: msg.operator,
            callsign: msg.callsign,
            target_call: msg.target_call,
            target_name: msg.target_name,
          });
          setMessages((prev) => [
            ...prev,
            {
              id: nextId(),
              timestamp: formatTime(),
              kind: 'tx',
              sender: msg.callsign,
              text: resolvedText,
            },
          ]);
        }
        break;
      }

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
        sendRef.current({ type: 'list_journals' });
        break;

      case 'journal_deleted':
        setJournals((prev) => prev.filter((j) => j._file !== msg.file_path));
        break;

      case 'spectrogram_row':
        spectroRef.current?.pushRow(msg.row, msg.vad, msg.squelch);
        break;

      case 'pending_stations':
        setPendingStations(msg.stations);
        break;

      case 'online_status':
        setIsOnline(msg.online);
        break;

      case 'contact_auto_added':
        break;

      case 'fcc_lookup_result':
        setFccLookupResult(msg);
        break;

      case 'verify_all_complete':
        setVerifyAllComplete(true);
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

  function handleToggleServiceMode() {
    const next = serviceMode === 'GMRS' ? 'FRS' : 'GMRS';
    send({ type: 'set_service_mode', service: next });
  }

  function handleToggleListenOnly() {
    send({ type: 'set_listen_only', listen_only: !listenOnly });
  }

  function handleToggleProfanity() {
    send({ type: 'set_config', filter_profanity: !filterProfanity });
  }

  function handleToggleFuzzy() {
    send({ type: 'set_config', fuzzy_callsign: !fuzzyCallsign });
  }

  function handleSinkChange(sink: string) {
    setSystemMonitorSinkLocal(sink);
    send({ type: 'set_config', system_monitor_sink: sink });
  }

  function handleVoiceTest() {
    send({ type: 'voice_preview' });
  }

  function handleSpectroColormapChange(cm: 'viridis' | 'grayscale') {
    setSpectroColormap(cm);
    send({ type: 'set_spectro_config', colormap: cm });
  }

  function handleSpectroFreqRangeChange(range: 'voice' | 'full') {
    setSpectroFreqRange(range);
    send({ type: 'set_spectro_config', freq_range: range });
  }

  function handleSpectroTimeWindowChange(s: number) {
    setSpectroTimeWindowS(s);
    send({ type: 'set_spectro_config', time_window_s: s });
  }

  // Add pending station → open contacts dialog pre-filled
  function handleAddPending(station: PendingStation) {
    setPendingPrefilledCallsign(station.callsign);
    setShowContacts(true);
  }

  // When contacts dialog closes, clear the prefilled callsign
  function handleContactsClose() {
    setShowContacts(false);
    setPendingPrefilledCallsign(undefined);
    setFccLookupResult(null);
  }

  const rxMessages = messages.filter((m) => m.kind === 'rx' && !m.partial);
  const rxTexts = rxMessages.map((m) => (m.sender ? `[${m.sender}] ${m.text}` : m.text));
  const rxCallsigns = [...new Set(
    rxMessages.map((m) => m.sender).filter(Boolean) as string[]
  )];

  const stationStatus = connected ? 'READY' : 'OFFLINE';
  const showCallsignChips = serviceMode === 'GMRS';

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box
        className="app-shell"
        sx={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
      >
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
          isOnline={isOnline}
          serviceMode={serviceMode}
          listenOnly={listenOnly}
          onChangeOperator={() => setShowModal(true)}
          showAttendance={showAttendance}
          onToggleAttendance={() => setShowAttendance((v) => !v)}
          showJournal={showJournal}
          onToggleJournal={() => setShowJournal((v) => !v)}
          showContacts={showContacts}
          onToggleContacts={() => {
            if (showContacts) handleContactsClose();
            else setShowContacts(true);
          }}
          showConfig={showConfig}
          onToggleConfig={() => setShowConfig((v) => !v)}
          darkMode={darkMode}
          onToggleDark={handleToggleDark}
          touchMode={touchMode}
          onToggleTouch={handleToggleTouch}
          onToggleServiceMode={handleToggleServiceMode}
          onToggleListenOnly={handleToggleListenOnly}
        />

        {showConfig && (
          <ConfigPanel
            filterProfanity={filterProfanity}
            fuzzyCallsign={fuzzyCallsign}
            systemMonitorSink={systemMonitorSink}
            spectroColormap={spectroColormap}
            spectroFreqRange={spectroFreqRange}
            spectroTimeWindowS={spectroTimeWindowS}
            onToggleProfanity={handleToggleProfanity}
            onToggleFuzzy={handleToggleFuzzy}
            onSinkChange={handleSinkChange}
            onVoiceTest={handleVoiceTest}
            onSpectroColormapChange={handleSpectroColormapChange}
            onSpectroFreqRangeChange={handleSpectroFreqRangeChange}
            onSpectroTimeWindowChange={handleSpectroTimeWindowChange}
          />
        )}

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

        <PendingStationsBar
          stations={pendingStations}
          onAdd={handleAddPending}
          onDismiss={(cs) => send({ type: 'dismiss_pending', callsign: cs })}
          onDismissAll={() => send({ type: 'dismiss_all_pending' })}
        />

        <ChatDisplay
          entries={messages}
          contacts={contacts}
          showCallsignChips={showCallsignChips}
        />

        <Spectrogram
          ref={spectroRef}
          colormap={spectroColormap}
          timeWindowS={spectroTimeWindowS}
        />

        <StatusRow status={radioStatus} />

        <QuickMessages
          operatorName={operator?.operatorName ?? ''}
          onSelect={(text) => messageInputRef.current?.setText(text)}
        />

        {!listenOnly && (
          <MessageInput
            ref={messageInputRef}
            transmitting={transmitting}
            contacts={contacts}
            myCallsign={operator?.callsign ?? ''}
            onSend={handleSend}
            onStandaloneId={() => {
              if (!operator) { setShowModal(true); return; }
              send({ type: 'standalone_id', operator: operator.operatorName, callsign: operator.callsign, location: operator.location });
            }}
          />
        )}

        <ContactsDialog
          open={showContacts}
          onClose={handleContactsClose}
          contacts={contacts}
          prefilledCallsign={pendingPrefilledCallsign}
          fccLookupResult={fccLookupResult}
          verifyAllComplete={verifyAllComplete}
          onSend={send}
          onVerifyAllDismiss={() => setVerifyAllComplete(false)}
        />
      </Box>
    </ThemeProvider>
  );
}
