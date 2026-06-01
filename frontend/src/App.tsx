import { useState, useCallback, useRef, useMemo } from 'react';
import { DndContext } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, arrayMove } from '@dnd-kit/sortable';
import { DraggablePanel } from './components/DraggablePanel/DraggablePanel';
import { ThemeProvider, CssBaseline, Box, CircularProgress, Snackbar, Alert } from '@mui/material';
import { makeTheme } from './theme';
import { useAuth } from './hooks/useAuth';
import { useWebSocket } from './hooks/useWebSocket';
import type {
  WsMessage,
  StatusMsg,
  TxMessagePayload,
  Contact,
  AttendanceStation,
  JournalEntry,
  FccLookupResultMsg,
  InputDeviceOption,
  MonitorSinkOption,
  UserProfile,
  VoiceOption,
} from './types/ws';
import { LoginScreen } from './components/LoginScreen/LoginScreen';
import { SetupScreen } from './components/SetupScreen/SetupScreen';
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
import { AdminPanel } from './components/AdminPanel/AdminPanel';
import { UsersPanel } from './components/UsersPanel/UsersPanel';
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
  const { token, profile, setProfile, loading: authLoading, setupNeeded, setup, login, logout } = useAuth();

  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [radioStatus, setRadioStatus] = useState<StatusMsg | null>(null);
  const [transmitting, setTransmitting] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [profiles, setProfiles] = useState<UserProfile[]>([]);
  const inProgressRef = useRef<Map<string, string>>(new Map());
  const sendRef = useRef<(p: unknown) => void>(() => {});
  const messageInputRef = useRef<MessageInputHandle>(null);
  const spectroRef = useRef<SpectrogramHandle>(null);
  const profileRef = useRef(profile);
  profileRef.current = profile;

  // Panel visibility
  const [showAttendance, setShowAttendance] = useState(false);
  const [showJournal, setShowJournal] = useState(false);
  const [showContacts, setShowContacts] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);

  // Panel order — initialized from localStorage to avoid FOUC; overridden by profile on load
  const [panelOrder, setPanelOrder] = useState<string[]>(
    () => {
      try {
        return JSON.parse(localStorage.getItem('radio_tty_panel_order') ?? '["config","attendance","journal"]');
      } catch { return ['config', 'attendance', 'journal']; }
    }
  );

  // Dark mode — initialized from localStorage to avoid FOUC; overridden by profile on load
  const [darkMode, setDarkMode] = useState(
    () => localStorage.getItem('radio_tty_dark_mode') === 'true'
  );
  const theme = useMemo(() => makeTheme(darkMode), [darkMode]);

  // Attendance
  const [attendanceStations, setAttendanceStations] = useState<AttendanceStation[]>([]);

  // Journals
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [journalResult, setJournalResult] = useState<JournalResultDraft | null>(null);
  const [journalGenerating, setJournalGenerating] = useState(false);
  const [journalError, setJournalError] = useState<string | null>(null);

  // Publish snackbar
  const [publishSnack, setPublishSnack] = useState<string | null>(null);

  // FCC / Callsigns
  const [pendingStations, setPendingStations] = useState<PendingStation[]>([]);
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [fccLookupResult, setFccLookupResult] = useState<FccLookupResultMsg | null>(null);
  const [verifyAllComplete, setVerifyAllComplete] = useState(false);
  const [pendingPrefilledCallsign, setPendingPrefilledCallsign] = useState<string | undefined>();

  // Per-user prefs (synced from user_profile message)
  const [listenOnly, setListenOnly] = useState(false);
  const [filterProfanity, setFilterProfanity] = useState(true);
  const [spectroColormap, setSpectroColormap] = useState<'viridis' | 'grayscale'>('viridis');
  const [spectroTimeWindowS, setSpectroTimeWindowS] = useState(30);

  // Available TTS voices (sent by server on connect)
  const [voices, setVoices] = useState<VoiceOption[]>([]);

  // Station-wide settings (synced from status message)
  const [sttListening, setSttListening] = useState(true);
  const [serviceMode, setServiceMode] = useState('GMRS');
  const [fuzzyCallsign, setFuzzyCallsign] = useState(false);
  const [inputDevice, setInputDevice] = useState<string | number>(-1);
  const [systemMonitorSink, setSystemMonitorSink] = useState('');
  const [inputDevices, setInputDevices] = useState<InputDeviceOption[]>([]);
  const [monitorSinks, setMonitorSinks] = useState<MonitorSinkOption[]>([]);
  const [spectroFreqRange, setSpectroFreqRange] = useState<'voice' | 'full'>('full');

  // Admin config (synced from server status message)
  const [adminConfig, setAdminConfig] = useState({
    stationCallsign: 'N0CALL',
    stationName: '',
    stationLocation: '',
    stationVoice: '',
    geminiApiKeySet: false,
    journalsDir: '/data/journals',
  });

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
              },
            ];
          });
        }
        break;
      }

      case 'status':
        setRadioStatus(msg);
        // Per-user fields (listen_only, filter_profanity, spectro_colormap, spectro_time_window_s)
        // are now set from user_profile messages — not from status.
        if (msg.stt_listening !== undefined) setSttListening(msg.stt_listening);
        if (msg.service_mode !== undefined) setServiceMode(msg.service_mode);
        if (msg.fuzzy_callsign !== undefined) setFuzzyCallsign(msg.fuzzy_callsign);
        if (msg.input_device !== undefined) setInputDevice(msg.input_device);
        if (msg.system_monitor_sink !== undefined) setSystemMonitorSink(msg.system_monitor_sink);
        if (msg.spectro_freq_range === 'voice' || msg.spectro_freq_range === 'full')
          setSpectroFreqRange(msg.spectro_freq_range);
        setAdminConfig((prev) => ({
          stationCallsign: msg.station_callsign ?? prev.stationCallsign,
          stationName: msg.station_name ?? prev.stationName,
          stationLocation: msg.station_location ?? prev.stationLocation,
          stationVoice: msg.station_voice ?? prev.stationVoice,
          geminiApiKeySet: msg.gemini_api_key_set ?? prev.geminiApiKeySet,
          journalsDir: msg.journals_dir ?? prev.journalsDir,
        }));
        break;

      case 'user_profile': {
        const p = msg.profile;
        setProfile(p);
        // Apply per-user prefs from the profile
        const prefs = p.prefs;
        if (prefs.dark_mode !== undefined) {
          setDarkMode(prefs.dark_mode);
          localStorage.setItem('radio_tty_dark_mode', String(prefs.dark_mode));
        }
        if (prefs.panel_order) {
          setPanelOrder(prefs.panel_order);
          localStorage.setItem('radio_tty_panel_order', JSON.stringify(prefs.panel_order));
        }
        if (prefs.filter_profanity !== undefined) setFilterProfanity(prefs.filter_profanity);
        if (prefs.listen_only !== undefined) setListenOnly(prefs.listen_only);
        if (prefs.spectro_colormap) setSpectroColormap(prefs.spectro_colormap);
        if (prefs.spectro_time_window_s) setSpectroTimeWindowS(prefs.spectro_time_window_s);
        break;
      }

      case 'profiles':
        setProfiles(msg.profiles);
        break;

      case 'tx_status':
        setTransmitting(msg.status === 'transmitting');
        break;

      case 'tx_echo':
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            timestamp: formatTime(msg.ts),
            kind: 'tx',
            sender: msg.display_name || msg.operator || msg.callsign,
            text: msg.text,
          },
        ]);
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

      case 'journal_published':
        setPublishSnack(`"${msg.title}" published to /journal`);
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

      case 'input_devices':
        setInputDevices(msg.devices);
        setMonitorSinks(msg.monitor_sinks);
        setInputDevice(msg.current_input_device);
        setSystemMonitorSink(msg.current_monitor_sink);
        break;

      case 'voices_list':
        setVoices(msg.voices);
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
  }, [setProfile]);

  const handleWsOpen = useCallback(() => {
    // Request input device list whenever the socket connects or reconnects.
    sendRef.current({ type: 'list_input_devices' });
    sendRef.current({ type: 'list_profiles' });
  }, []);

  const { send, connected } = useWebSocket({
    onMessage: handleWsMessage,
    token,
    onOpen: handleWsOpen,
  });
  sendRef.current = send;

  const handleEnrollCluster = useCallback((clusterLabel: string, callsign: string) => {
    sendRef.current({ type: 'enroll_speaker', callsign, cluster_label: clusterLabel });
  }, []);

  function handleSend(text: string, targetCall: string, targetName: string) {
    if (!profile) return;
    const payload: TxMessagePayload = {
      type: 'tx_message',
      text,
      operator: profile.operator_name,
      callsign: effectiveCallsign,
      target_call: targetCall,
      target_name: targetName,
    };
    send(payload);
  }

  function handleToggleServiceMode() {
    const next = serviceMode === 'GMRS' ? 'FRS' : 'GMRS';
    send({ type: 'set_service_mode', service: next });
  }

  function handleToggleListenOnly() {
    const next = !listenOnly;
    setListenOnly(next);
    send({ type: 'set_listen_only', listen_only: next });
  }

  function handleToggleSttListening() {
    send({ type: 'set_stt_listening', listening: !sttListening });
  }

  function handleToggleProfanity() {
    const next = !filterProfanity;
    setFilterProfanity(next);
    send({ type: 'set_config', filter_profanity: next });
  }

  function handleToggleFuzzy() {
    send({ type: 'set_config', fuzzy_callsign: !fuzzyCallsign });
  }

  function handleInputDeviceChange(device: string | number, sink: string) {
    setInputDevice(device);
    setSystemMonitorSink(sink);
    send({ type: 'set_input_device', input_device: device, system_monitor_sink: sink });
  }

  function handleVoiceTest() {
    send({ type: 'voice_preview' });
  }

  function handlePreviewVoice(voiceId: string) {
    send({ type: 'voice_preview', voice: voiceId });
  }

  function handleSaveVoicePref(voiceId: string) {
    send({ type: 'save_user_prefs', prefs: { tts_voice: voiceId } });
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

  function handleAdminSave(values: {
    callsign: string;
    name: string;
    location: string;
    voice: string;
    gemini_api_key: string;
    journals_dir: string;
  }) {
    send({ type: 'set_admin_config', ...values });
  }

  function handleToggleDark() {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem('radio_tty_dark_mode', String(next));
    send({ type: 'save_user_prefs', prefs: { dark_mode: next } });
  }

  function handleClearChat() {
    setMessages([]);
  }

  function handleAddPending(station: PendingStation) {
    setPendingPrefilledCallsign(station.callsign);
    setShowContacts(true);
  }

  function handleContactsClose() {
    setShowContacts(false);
    setPendingPrefilledCallsign(undefined);
    setFccLookupResult(null);
  }

  function handleUpdateProfile(updates: {
    operator_name?: string;
    callsign?: string;
    location?: string;
    avatar_emoji?: string;
  }) {
    send({ type: 'update_profile', user_id: profile?.id, ...updates });
  }

  function handleChangePassword(newPassword: string) {
    send({ type: 'update_profile', user_id: profile?.id, new_password: newPassword });
  }

  async function handleLogout() {
    await logout();
  }

  const rxMessages = useMemo(
    () => messages.filter((m) => m.kind === 'rx' && !m.partial),
    [messages]
  );
  const rxTexts = useMemo(
    () => rxMessages.map((m) => (m.sender ? `[${m.sender}] ${m.text}` : m.text)),
    [rxMessages]
  );
  const rxCallsigns = useMemo(
    () => [...new Set(rxMessages.map((m) => m.sender).filter(Boolean) as string[])],
    [rxMessages]
  );

  function handlePanelDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setPanelOrder((prev) => {
        const oldIndex = prev.indexOf(String(active.id));
        const newIndex = prev.indexOf(String(over.id));
        const next = arrayMove(prev, oldIndex, newIndex);
        localStorage.setItem('radio_tty_panel_order', JSON.stringify(next));
        send({ type: 'save_user_prefs', prefs: { panel_order: next } });
        return next;
      });
    }
  }

  const handleListJournals = useCallback(() => {
    send({ type: 'list_journals' });
  }, [send]);

  const handleGenerate = useCallback((transcript: string, callsigns: string[]) => {
    setJournalGenerating(true);
    setJournalError(null);
    setJournalResult(null);
    send({ type: 'generate_journal', transcript, callsigns });
  }, [send]);

  const handleSaveJournal = useCallback((
    title: string,
    summary: string,
    callsigns_locations: Array<{ callsign: string; location: string }>,
    transcript: string,
  ) => {
    send({ type: 'save_journal', title, summary, callsigns_locations, transcript });
  }, [send]);

  const handleDeleteJournal = useCallback((file_path: string) => {
    send({ type: 'delete_journal', file_path });
  }, [send]);

  const handlePublishJournal = useCallback((file_path: string) => {
    send({ type: 'publish_journal', file_path });
  }, [send]);

  const handleDismissJournalResult = useCallback(() => {
    setJournalResult(null);
  }, []);

  const handleClearAttendance = useCallback(() => {
    send({ type: 'clear_attendance' });
  }, [send]);

  const effectiveCallsign = profile?.callsign || adminConfig.stationCallsign;
  const stationStatus = connected ? 'READY' : 'OFFLINE';
  const showCallsignChips = serviceMode === 'GMRS';

  // Show a blank screen while validating existing token on startup.
  if (authLoading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      </ThemeProvider>
    );
  }

  // First-run: no users exist yet — collect admin profile before anything else.
  if (setupNeeded) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <SetupScreen onSetup={setup} />
      </ThemeProvider>
    );
  }

  // Show login screen when not authenticated.
  if (!profile || !token) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <LoginScreen onLogin={login} />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box
        className="app-shell"
        sx={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
      >
        <TopBar
          profile={profile}
          stationStatus={stationStatus}
          connected={connected}
          isOnline={isOnline}
          serviceMode={serviceMode}
          listenOnly={listenOnly}
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
          showAdmin={showAdmin}
          onToggleAdmin={() => setShowAdmin((v) => !v)}
          darkMode={darkMode}
          onToggleDark={handleToggleDark}
          onToggleServiceMode={handleToggleServiceMode}
          onToggleListenOnly={handleToggleListenOnly}
          sttListening={sttListening}
          onToggleSttListening={handleToggleSttListening}
          onClearChat={handleClearChat}
          onUpdateProfile={handleUpdateProfile}
          onChangePassword={handleChangePassword}
          onLogout={handleLogout}
          voices={voices}
          onPreviewVoice={handlePreviewVoice}
          onSaveVoicePref={handleSaveVoicePref}
        />

        <DndContext onDragEnd={handlePanelDragEnd}>
          <SortableContext items={panelOrder} strategy={verticalListSortingStrategy}>
            {panelOrder.map((id) => {
              if (id === 'config' && showConfig) {
                return (
                  <DraggablePanel key="config" id="config">
                    <ConfigPanel
                      filterProfanity={filterProfanity}
                      fuzzyCallsign={fuzzyCallsign}
                      inputDevice={inputDevice}
                      systemMonitorSink={systemMonitorSink}
                      inputDevices={inputDevices}
                      monitorSinks={monitorSinks}
                      spectroColormap={spectroColormap}
                      spectroFreqRange={spectroFreqRange}
                      spectroTimeWindowS={spectroTimeWindowS}
                      onToggleProfanity={handleToggleProfanity}
                      onToggleFuzzy={handleToggleFuzzy}
                      onInputDeviceChange={handleInputDeviceChange}
                      onVoiceTest={handleVoiceTest}
                      onSpectroColormapChange={handleSpectroColormapChange}
                      onSpectroFreqRangeChange={handleSpectroFreqRangeChange}
                      onSpectroTimeWindowChange={handleSpectroTimeWindowChange}
                    />
                  </DraggablePanel>
                );
              }
              if (id === 'attendance' && showAttendance) {
                return (
                  <DraggablePanel key="attendance" id="attendance">
                    <AttendancePanel
                      stations={attendanceStations}
                      onClear={handleClearAttendance}
                    />
                  </DraggablePanel>
                );
              }
              if (id === 'journal' && showJournal) {
                return (
                  <DraggablePanel key="journal" id="journal">
                    <JournalPanel
                      journals={journals}
                      pendingResult={journalResult}
                      generating={journalGenerating}
                      journalError={journalError}
                      rxTexts={rxTexts}
                      rxCallsigns={rxCallsigns}
                      onListJournals={handleListJournals}
                      onGenerate={handleGenerate}
                      onSave={handleSaveJournal}
                      onDelete={handleDeleteJournal}
                      onPublish={handlePublishJournal}
                      onDismissResult={handleDismissJournalResult}
                    />
                  </DraggablePanel>
                );
              }
              return null;
            })}
          </SortableContext>
        </DndContext>

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
          onEnrollCluster={handleEnrollCluster}
        />

        <Spectrogram
          ref={spectroRef}
          colormap={spectroColormap}
          timeWindowS={spectroTimeWindowS}
        />

        <StatusRow status={radioStatus} />

        {!listenOnly && (
          <QuickMessages
            operatorName={profile.operator_name}
            onSelect={(text) => messageInputRef.current?.setText(text)}
          />
        )}

        {!listenOnly && (
          <MessageInput
            ref={messageInputRef}
            transmitting={transmitting}
            contacts={contacts}
            myCallsign={effectiveCallsign}
            onSend={handleSend}
            onStandaloneId={() => {
              send({
                type: 'standalone_id',
                operator: profile.operator_name,
                callsign: effectiveCallsign,
                location: profile.location,
              });
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

        <AdminPanel
          open={showAdmin}
          onClose={() => setShowAdmin(false)}
          config={adminConfig}
          voices={voices}
          onSave={handleAdminSave}
          onPreviewVoice={handlePreviewVoice}
        >
          {profile.is_admin && (
            <UsersPanel
              profiles={profiles}
              currentUserId={profile.id}
              onCreateProfile={(data) => send({ type: 'create_profile', ...data })}
              onDeleteProfile={(userId) => send({ type: 'delete_profile', user_id: userId })}
              onResetLockout={(userId) => send({ type: 'reset_lockout', user_id: userId })}
            />
          )}
        </AdminPanel>

        <Snackbar
          open={publishSnack !== null}
          autoHideDuration={5000}
          onClose={() => setPublishSnack(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert
            onClose={() => setPublishSnack(null)}
            severity="success"
            sx={{ width: '100%' }}
          >
            {publishSnack}
          </Alert>
        </Snackbar>
      </Box>
    </ThemeProvider>
  );
}
