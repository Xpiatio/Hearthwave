import { useState, useCallback, useRef, useMemo } from 'react';
import type { DragEndEvent } from '@dnd-kit/core';
import { arrayMove } from '@dnd-kit/sortable';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import { makeTheme } from './theme';
import { useAuth } from './hooks/useAuth';
import { useWebSocket } from './hooks/useWebSocket';
import type {
  WsMessage,
  StatusMsg,
  TxMessagePayload,
  ChatMessagePayload,
  Contact,
  AttendanceStation,
  JournalEntry,
  FccLookupResultMsg,
  InputDeviceOption,
  MonitorSinkOption,
  OutputDeviceOption,
  UserProfile,
  VoiceOption,
  VoiceTxStartPayload,
  VoiceTxChunkPayload,
  VoiceTxEndPayload,
  VoiceTxCancelPayload,
  TxAbortPayload,
} from './types/ws';
import type { ChatEntry } from './components/ChatDisplay/ChatDisplay';
import type { SpectrogramHandle } from './components/Spectrogram/Spectrogram';
import type { ServerConfig, ServerConfigSaveValues } from './components/ServerConfigPanel/ServerConfigPanel';
import { LoginScreen } from './components/LoginScreen/LoginScreen';
import { SetupScreen } from './components/SetupScreen/SetupScreen';
import { DesktopApp } from './components/DesktopApp/DesktopApp';
import { MobileApp } from './components/MobileApp/MobileApp';
import { useMobileDetect } from './hooks/useMobileDetect';
import './App.css';

let entryCounter = 0;
function nextId() {
  return `msg-${++entryCounter}`;
}

function formatTime(isoOrNow?: string): string {
  const d = isoOrNow ? new Date(isoOrNow) : new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function normalizeForDedup(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, ' ');
}

function isNearDuplicate(a: string, b: string): boolean {
  const na = normalizeForDedup(a);
  const nb = normalizeForDedup(b);
  if (na === nb) return true;
  const [shorter, longer] = na.length <= nb.length ? [na, nb] : [nb, na];
  if (shorter.length < 20) return false;
  if (longer.startsWith(shorter)) {
    return shorter.length === longer.length || longer[shorter.length] === ' ';
  }
  return false;
}

function removeAdjacentDuplicates(entries: ChatEntry[], newText: string): ChatEntry[] {
  for (let i = entries.length - 1; i >= Math.max(0, entries.length - 3); i--) {
    if (entries[i].kind === 'rx' && isNearDuplicate(entries[i].text, newText)) {
      return [...entries.slice(0, i), ...entries.slice(i + 1)];
    }
  }
  return entries;
}

function pruneMap<K, V>(map: Map<K, V>, maxSize: number): void {
  while (map.size > maxSize) {
    map.delete(map.keys().next().value as K);
  }
}

import type { JournalResultDraft, PendingStation, PromptState } from './types/appTypes';
import { TokenPromptDialog } from './components/TokenPromptDialog/TokenPromptDialog';

export default function App() {
  const { token, profile, setProfile, loading: authLoading, setupNeeded, setup, login, logout } = useAuth();

  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [radioStatus, setRadioStatus] = useState<StatusMsg | null>(null);
  const [transmitting, setTransmitting] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [profiles, setProfiles] = useState<UserProfile[]>([]);
  const inProgressRef = useRef<Map<string, string>>(new Map());
  const recentFinalIdsRef = useRef<Map<string, string>>(new Map());
  const sendRef = useRef<(p: unknown) => void>(() => {});
  const spectroRef = useRef<SpectrogramHandle>(null);
  const profileRef = useRef(profile);
  profileRef.current = profile;
  const pendingTranscriptRef = useRef<string>('');

  // Panel visibility
  const [showAttendance, setShowAttendance] = useState(false);
  const [showJournal, setShowJournal] = useState(false);
  const [showContacts, setShowContacts] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [showServerConfig, setShowServerConfig] = useState(false);
  const [serverConfig, setServerConfig] = useState<ServerConfig>({
    vadThreshold: 0.5,
    whisperModel: 'small.en',
    whisperModelFinal: '',
    squelchAdaptive: false,
    sttDebugCapture: false,
    txConditioning: false,
    pttMode: 'manual',
    pttSerialPort: '',
    pttSerialLine: 'RTS',
    monitorPassthrough: false,
    attendanceEnabled: false,
    savedPhrases: [],
  });

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

  // Waterfall visibility — persisted locally; defaults to visible
  const [showWaterfall, setShowWaterfall] = useState(
    () => localStorage.getItem('radio_tty_show_waterfall') !== 'false'
  );
  const theme = useMemo(() => makeTheme(darkMode), [darkMode]);

  // Attendance
  const [attendanceStations, setAttendanceStations] = useState<AttendanceStation[]>([]);

  // Journals
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [journalResult, setJournalResult] = useState<JournalResultDraft | null>(null);
  const [journalGenerating, setJournalGenerating] = useState(false);
  const [journalError, setJournalError] = useState<string | null>(null);

  // Snackbars
  const [publishSnack, setPublishSnack] = useState<string | null>(null);
  const [errorSnack, setErrorSnack] = useState<string | null>(null);
  const [journalSavedSnack, setJournalSavedSnack] = useState<string | null>(null);
  const [voicePreviewBusy, setVoicePreviewBusy] = useState(false);

  // FCC / Callsigns
  const [pendingStations, setPendingStations] = useState<PendingStation[]>([]);
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [fccLookupResult, setFccLookupResult] = useState<FccLookupResultMsg | null>(null);
  const [verifyAllComplete, setVerifyAllComplete] = useState(false);

  // Token prompt dialog state
  const [promptState, setPromptState] = useState<PromptState | null>(null);
  const [pendingPrefilledCallsign, setPendingPrefilledCallsign] = useState<string | undefined>();
  const [pendingPrefilledName, setPendingPrefilledName] = useState<string | undefined>();
  const [pendingPrefilledLocation, setPendingPrefilledLocation] = useState<string | undefined>();

  // Per-user prefs (synced from user_profile message)
  const [listenOnly, setListenOnly] = useState(false);
  const [readAloud, setReadAloud] = useState(false);
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const notificationsEnabledRef = useRef(false);
  notificationsEnabledRef.current = notificationsEnabled;
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
  const [outputDevice, setOutputDevice] = useState<number>(-1);
  const [outputDevices, setOutputDevices] = useState<OutputDeviceOption[]>([]);
  const [spectroFreqRange, setSpectroFreqRange] = useState<'voice' | 'full'>('full');

  // Admin config (synced from server status message)
  const [adminConfig, setAdminConfig] = useState({
    stationCallsign: 'N0CALL',
    stationName: '',
    stationLocation: '',
    stationVoice: '',
    stationLengthScale: 1.0,
    geminiApiKeySet: false,
    journalsDir: '/data/journals',
    ncsZone: '',
    rxMode: 'voice',
  });

  // Plugin infrastructure — last WS message forwarded to mounted plugin panels
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const [channelClear, setChannelClear] = useState(true);

  // NCS panel visibility (admin-only toggle)
  const [showNcs, setShowNcs] = useState(false);

  const handleWsMessage = useCallback((msg: WsMessage) => {
    setLastMessage(msg);
    switch (msg.type) {
      case 'rx_message': {
        const uid = msg.utterance_id;
        if (msg.partial) {
          const existingId = inProgressRef.current.get(uid);
          if (existingId) {
            setMessages((prev) =>
              prev.map((e) =>
                e.id === existingId
                  ? { ...e, text: msg.text, partial: true, callsign_spans: msg.callsign_spans, source: msg.source }
                  : e
              )
            );
          } else {
            const id = nextId();
            inProgressRef.current.set(uid, id);
            setMessages((prev) => [
              ...removeAdjacentDuplicates(prev, msg.text),
              {
                id,
                timestamp: formatTime(msg.ts),
                kind: 'rx',
                sender: msg.from || msg.callsign || undefined,
                text: msg.text,
                partial: true,
                callsign_spans: msg.callsign_spans,
                source: msg.source,
              },
            ]);
          }
        } else {
          const existingId = inProgressRef.current.get(uid);
          inProgressRef.current.delete(uid);
          if (existingId) {
            recentFinalIdsRef.current.set(uid, existingId);
            pruneMap(recentFinalIdsRef.current, 10);
            setMessages((prev) =>
              prev.map((e) =>
                e.id === existingId
                  ? {
                      ...e,
                      text: msg.text,
                      partial: false,
                      callsign_spans: msg.callsign_spans,
                      source: msg.source,
                    }
                  : e
              )
            );
          } else {
            const id = nextId();
            recentFinalIdsRef.current.set(uid, id);
            pruneMap(recentFinalIdsRef.current, 10);
            setMessages((prev) => [
              ...removeAdjacentDuplicates(prev, msg.text),
              {
                id,
                timestamp: formatTime(msg.ts),
                kind: 'rx',
                sender: msg.from || msg.callsign || undefined,
                text: msg.text,
                callsign_spans: msg.callsign_spans,
                source: msg.source,
              },
            ]);
          }
          if (
            notificationsEnabledRef.current &&
            Notification.permission === 'granted' &&
            document.visibilityState === 'hidden'
          ) {
            const sender = msg.callsign || msg.from || 'Station';
            new Notification(`📻 ${sender}`, {
              body: msg.text.slice(0, 120),
              tag: `rx-${msg.utterance_id}`,
              silent: true,
            });
          }
        }
        break;
      }

      case 'rx_message_patch': {
        const entryId = recentFinalIdsRef.current.get(msg.utterance_id);
        if (entryId) {
          setMessages((prev) =>
            prev.map((e) =>
              e.id === entryId
                ? { ...e, callsign_spans: [...(e.callsign_spans ?? []), ...msg.callsign_spans].sort((a, b) => a[0] - b[0]) }
                : e
            )
          );
        }
        break;
      }

      case 'status':
        setRadioStatus(msg);
        if (msg.channel_clear !== undefined) setChannelClear(msg.channel_clear);
        // Per-user fields (listen_only, filter_profanity, spectro_colormap, spectro_time_window_s)
        // are now set from user_profile messages — not from status.
        if (msg.stt_listening !== undefined) setSttListening(msg.stt_listening);
        if (msg.service_mode !== undefined) setServiceMode(msg.service_mode);
        if (msg.fuzzy_callsign !== undefined) setFuzzyCallsign(msg.fuzzy_callsign);
        if (msg.input_device !== undefined) setInputDevice(msg.input_device);
        if (msg.output_device !== undefined) setOutputDevice(msg.output_device);
        if (msg.system_monitor_sink !== undefined) setSystemMonitorSink(msg.system_monitor_sink);
        if (msg.spectro_freq_range === 'voice' || msg.spectro_freq_range === 'full')
          setSpectroFreqRange(msg.spectro_freq_range);
        setAdminConfig((prev) => ({
          stationCallsign: msg.station_callsign ?? prev.stationCallsign,
          stationName: msg.station_name ?? prev.stationName,
          stationLocation: msg.station_location ?? prev.stationLocation,
          stationVoice: msg.station_voice ?? prev.stationVoice,
          stationLengthScale: msg.station_length_scale ?? prev.stationLengthScale,
          geminiApiKeySet: msg.gemini_api_key_set ?? prev.geminiApiKeySet,
          journalsDir: msg.journals_dir ?? prev.journalsDir,
          ncsZone: msg.ncs_zone ?? prev.ncsZone,
          rxMode: msg.rx_mode ?? prev.rxMode,
        }));
        setServerConfig((prev) => ({
          vadThreshold: msg.vad_threshold ?? prev.vadThreshold,
          whisperModel: msg.whisper_model ?? prev.whisperModel,
          whisperModelFinal: msg.whisper_model_final ?? prev.whisperModelFinal,
          squelchAdaptive: msg.squelch_adaptive ?? prev.squelchAdaptive,
          sttDebugCapture: msg.stt_debug_capture ?? prev.sttDebugCapture,
          txConditioning: msg.tx_conditioning ?? prev.txConditioning,
          pttMode: msg.ptt_mode ?? prev.pttMode,
          pttSerialPort: msg.ptt_serial_port ?? prev.pttSerialPort,
          pttSerialLine: msg.ptt_serial_line ?? prev.pttSerialLine,
          monitorPassthrough: msg.monitor_passthrough ?? prev.monitorPassthrough,
          attendanceEnabled: msg.attendance_enabled ?? prev.attendanceEnabled,
          savedPhrases: msg.saved_phrases ?? prev.savedPhrases,
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
        if (prefs.read_aloud !== undefined) setReadAloud(prefs.read_aloud);
        if (prefs.notifications_enabled !== undefined) setNotificationsEnabled(prefs.notifications_enabled);
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

      case 'tx_echo': {
        const recipient =
          msg.target_call && msg.target_call !== 'ALL'
            ? msg.target_name
              ? `${msg.target_call} — ${msg.target_name}`
              : msg.target_call
            : undefined;
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            timestamp: formatTime(msg.ts),
            kind: 'tx',
            sender: msg.display_name || msg.operator || msg.callsign,
            recipient,
            text: msg.text,
          },
        ]);
        break;
      }

      case 'chat_echo':
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            timestamp: formatTime(msg.ts),
            kind: 'chat',
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

      case 'prompt_token':
        setPromptState({
          tokens: msg.tokens,
          originalText: msg.original_text,
          operator: msg.operator,
          callsign: msg.callsign,
          targetCall: msg.target_call,
          targetName: msg.target_name,
        });
        break;

      case 'session_attendance':
        setAttendanceStations(msg.stations);
        break;

      case 'journals':
        setJournals(msg.journals);
        break;

      case 'journal_result':
        sendRef.current({
          type: 'save_journal',
          title: msg.title,
          summary: msg.summary,
          callsigns_locations: msg.callsigns_locations,
          transcript: pendingTranscriptRef.current,
        });
        setJournalGenerating(false);
        setJournalError(null);
        break;

      case 'journal_error':
        setJournalError(msg.detail);
        setJournalGenerating(false);
        break;

      case 'journal_saved':
        setJournalSavedSnack('Journal saved');
        sendRef.current({ type: 'list_journals' });
        break;

      case 'journal_published':
        setPublishSnack(`"${msg.title}" published to /journal`);
        sendRef.current({ type: 'list_journals' });
        break;

      case 'journal_unpublished':
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

      case 'input_devices':
        setInputDevices(msg.devices);
        setMonitorSinks(msg.monitor_sinks);
        setInputDevice(msg.current_input_device);
        setSystemMonitorSink(msg.current_monitor_sink);
        break;

      case 'output_devices':
        setOutputDevices(msg.devices);
        setOutputDevice(msg.current_output_device);
        break;

      case 'voices_list':
        setVoices(msg.voices);
        break;

      case 'voice_preview_audio':
      case 'rx_audio': {
        // Decode base64 int16 PCM and play in the browser via Web Audio API.
        // voice_preview_audio lets a user audition their own TTS voice;
        // rx_audio plays incoming RX transcripts aloud (read_aloud pref).
        // Transmitted TX audio is NOT played in the browser — the server plays
        // it out the radio's sound device directly.
        try {
          const binary = atob(msg.data);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          const int16 = new Int16Array(bytes.buffer);
          const float32 = new Float32Array(int16.length);
          for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;
          const ctx = new AudioContext({ sampleRate: msg.sample_rate });
          const buf = ctx.createBuffer(1, float32.length, msg.sample_rate);
          buf.getChannelData(0).set(float32);
          const src = ctx.createBufferSource();
          src.buffer = buf;
          src.connect(ctx.destination);
          src.onended = () => { ctx.close(); };
          src.start();
        } catch (e) {
          console.error('audio playback error', e);
        }
        break;
      }

      case 'ncs_alert':
        if (
          notificationsEnabledRef.current &&
          Notification.permission === 'granted' &&
          document.visibilityState === 'hidden'
        ) {
          new Notification(`⚠️ SKYWARN: ${msg.event}`, {
            body: msg.headline.slice(0, 120),
            tag: `ncs-alert-${msg.id}`,
            silent: false,
          });
        }
        break;

      case 'voice_preview_done':
        setVoicePreviewBusy(false);
        break;

      case 'voice_tx_ack':
        break;

      case 'voice_tx_error':
        setErrorSnack(msg.detail);
        break;

      case 'error':
        setVoicePreviewBusy(false);
        setErrorSnack(msg.detail ?? 'An error occurred.');
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
    // Request input/output device lists whenever the socket connects or reconnects.
    sendRef.current({ type: 'list_input_devices' });
    sendRef.current({ type: 'list_output_devices' });
    sendRef.current({ type: 'list_profiles' });
  }, []);

  const { send, connected } = useWebSocket({
    onMessage: handleWsMessage,
    token,
    onOpen: handleWsOpen,
  });
  sendRef.current = send;


  function handleSend(text: string, targetCall: string, targetName: string) {
    if (!profile) return;
    const payload: TxMessagePayload = {
      type: 'tx_message',
      text,
      operator: profile.operator_name,
      callsign: effectiveCallsign,
      target_call: targetCall,
      target_name: targetName,
      // Transmit in this operator's profile voice/speed (the [tx] [name]
      // convention); the backend resolves it by display name.
      voice_as: profile.display_name,
    };
    send(payload);
  }

  function handleChat(text: string) {
    if (!profile) return;
    send({
      type: 'chat_message',
      text,
      operator: profile.operator_name,
      callsign: effectiveCallsign,
    } satisfies ChatMessagePayload);
  }

  function handleVoicePttStart() {
    if (!profile || !connected) return;
    send({ type: 'voice_tx_start', callsign: effectiveCallsign, operator: profile.operator_name } satisfies VoiceTxStartPayload);
  }
  function handleVoicePttChunk(b64: string) {
    send({ type: 'voice_tx_chunk', data: b64 } satisfies VoiceTxChunkPayload);
  }
  function handleVoicePttEnd() {
    send({ type: 'voice_tx_end' } satisfies VoiceTxEndPayload);
  }
  function handleVoicePttCancel() {
    send({ type: 'voice_tx_cancel' } satisfies VoiceTxCancelPayload);
  }

  function handleTxAbort() {
    send({ type: 'tx_abort' } satisfies TxAbortPayload);
    send({ type: 'voice_tx_cancel' } satisfies VoiceTxCancelPayload);
    setTransmitting(false);
  }

  function handleToggleServiceMode() {
    const next = serviceMode === 'GMRS' ? 'FRS' : 'GMRS';
    send({ type: 'set_service_mode', service: next });
  }

  function handleToggleReadAloud() {
    const next = !readAloud;
    setReadAloud(next);
    send({ type: 'save_user_prefs', prefs: { read_aloud: next } });
  }

  async function handleToggleNotifications() {
    if (notificationsEnabled) {
      setNotificationsEnabled(false);
      send({ type: 'save_user_prefs', prefs: { notifications_enabled: false } });
      return;
    }
    if (!('Notification' in window)) {
      setErrorSnack('Browser notifications are not supported.');
      return;
    }
    let permission = Notification.permission;
    if (permission === 'default') {
      permission = await Notification.requestPermission();
    }
    if (permission === 'granted') {
      setNotificationsEnabled(true);
      send({ type: 'save_user_prefs', prefs: { notifications_enabled: true } });
    } else {
      setErrorSnack('Notification permission denied. Enable it in browser settings.');
    }
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

  function handleOutputDeviceChange(device: number) {
    setOutputDevice(device);
    send({ type: 'set_output_device', output_device: device });
  }

  function handlePreviewVoice(voiceId: string) {
    setVoicePreviewBusy(true);
    send({ type: 'voice_preview', voice: voiceId });
  }

  function handleSaveTtsPrefs({ voice, length_scale }: { voice: string; length_scale: number }) {
    send({ type: 'save_user_prefs', prefs: { tts_voice: voice, tts_length_scale: length_scale } });
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
    tts_length_scale: number;
    gemini_api_key: string;
    journals_dir: string;
    ncs_zone: string;
    rx_mode: string;
  }) {
    send({ type: 'set_admin_config', ...values });
  }

  function handleServerConfigSave(values: ServerConfigSaveValues) {
    send({ type: 'set_server_config', ...values });
  }

  function handleToggleDark() {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem('radio_tty_dark_mode', String(next));
    send({ type: 'save_user_prefs', prefs: { dark_mode: next } });
  }

  function handleToggleWaterfall() {
    const next = !showWaterfall;
    setShowWaterfall(next);
    localStorage.setItem('radio_tty_show_waterfall', String(next));
  }

  function handleClearChat() {
    setMessages([]);
  }

  function handleTokenSubmit(resolvedText: string) {
    if (!promptState) return;
    send({
      type: 'tx_message',
      text: resolvedText,
      operator: promptState.operator,
      callsign: promptState.callsign,
      target_call: promptState.targetCall,
      target_name: promptState.targetName,
    });
    setPromptState(null);
  }

  function handleTokenCancel() {
    setPromptState(null);
  }

  function handleAddPending(station: PendingStation) {
    setPendingPrefilledCallsign(station.callsign);
    setPendingPrefilledName(station.name || undefined);
    setPendingPrefilledLocation(station.location || undefined);
    setShowContacts(true);
  }

  function handleContactsClose() {
    setShowContacts(false);
    setPendingPrefilledCallsign(undefined);
    setPendingPrefilledName(undefined);
    setPendingPrefilledLocation(undefined);
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

  function handlePanelMove(fromIndex: number, toIndex: number) {
    setPanelOrder((prev) => {
      const next = arrayMove(prev, fromIndex, toIndex);
      localStorage.setItem('radio_tty_panel_order', JSON.stringify(next));
      send({ type: 'save_user_prefs', prefs: { panel_order: next } });
      return next;
    });
  }

  const handleListJournals = useCallback(() => {
    send({ type: 'list_journals' });
  }, [send]);

  const handleGenerate = useCallback((transcript: string, callsigns: string[]) => {
    setJournalGenerating(true);
    setJournalError(null);
    setJournalResult(null);
    pendingTranscriptRef.current = transcript;
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

  const handleUnpublishJournal = useCallback((file_path: string) => {
    send({ type: 'unpublish_journal', file_path });
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

  function handleToggleAttendance() { setShowAttendance((v) => !v); }
  function handleToggleJournal() { setShowJournal((v) => !v); }
  function handleToggleContacts() {
    if (showContacts) handleContactsClose();
    else setShowContacts(true);
  }
  function handleToggleConfig() { setShowConfig((v) => !v); }
  function handleToggleAdmin() { setShowAdmin((v) => !v); }
  function handleToggleServerConfig() { setShowServerConfig((v) => !v); }
  function handleToggleNcs() {
    const next = !showNcs;
    setShowNcs(next);
    setPanelOrder((prev) =>
      next && !prev.includes('ncs') ? [...prev, 'ncs'] : prev.filter((id) => id !== 'ncs' || next)
    );
  }
  function handleDismissPending(cs: string) { send({ type: 'dismiss_pending', callsign: cs }); }
  function handleDismissAllPending() { send({ type: 'dismiss_all_pending' }); }
  function handleStandaloneId() {
    send({
      type: 'standalone_id',
      operator: profile!.operator_name,
      callsign: effectiveCallsign,
      location: profile!.location,
    });
  }
  function handleClosePublishSnack() { setPublishSnack(null); }
  function handleCloseErrorSnack() { setErrorSnack(null); }
  function handleCloseJournalSavedSnack() { setJournalSavedSnack(null); }
  function handleVerifyAllDismiss() { setVerifyAllComplete(false); }

  const isMobile = useMobileDetect();

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

  const sharedProps = {
    profile: profile!,
    profiles,
    connected,
    isOnline,
    showCallsignChips,
    messages,
    contacts,
    radioStatus,
    transmitting,
    lastMessage,
    channelClear,
    attendanceStations,
    onClearAttendance: handleClearAttendance,
    journals,
    journalResult,
    journalGenerating,
    journalError,
    rxTexts,
    rxCallsigns,
    onListJournals: handleListJournals,
    onGenerate: handleGenerate,
    onSaveJournal: handleSaveJournal,
    onDeleteJournal: handleDeleteJournal,
    onPublishJournal: handlePublishJournal,
    onUnpublishJournal: handleUnpublishJournal,
    onDismissJournalResult: handleDismissJournalResult,
    listenOnly,
    onSend: handleSend,
    onChat: handleChat,
    onStandaloneId: handleStandaloneId,
    onVoicePttStart: handleVoicePttStart,
    onVoicePttChunk: handleVoicePttChunk,
    onVoicePttEnd: handleVoicePttEnd,
    onVoicePttCancel: handleVoicePttCancel,
    onTxAbort: handleTxAbort,
    voices,
    voicePreviewBusy,
    onPreviewVoice: handlePreviewVoice,
    onSaveTtsPrefs: handleSaveTtsPrefs,
    onUpdateProfile: handleUpdateProfile,
    onChangePassword: handleChangePassword,
    onLogout: handleLogout,
    serviceMode,
    readAloud,
    notificationsEnabled,
    sttListening,
    darkMode,
    onToggleServiceMode: handleToggleServiceMode,
    onToggleListenOnly: handleToggleListenOnly,
    onToggleReadAloud: handleToggleReadAloud,
    onToggleNotifications: handleToggleNotifications,
    onToggleSttListening: handleToggleSttListening,
    onToggleDark: handleToggleDark,
    adminConfig,
    serverConfig,
    showConfig,
    showAdmin,
    showServerConfig,
    onToggleConfig: handleToggleConfig,
    onToggleAdmin: handleToggleAdmin,
    onToggleServerConfig: handleToggleServerConfig,
    onAdminSave: handleAdminSave,
    onServerConfigSave: handleServerConfigSave,
    showContacts,
    pendingPrefilledCallsign,
    pendingPrefilledName,
    pendingPrefilledLocation,
    fccLookupResult,
    verifyAllComplete,
    onContactsClose: handleContactsClose,
    onVerifyAllDismiss: handleVerifyAllDismiss,
    send,
    pendingStations,
    onAddPending: handleAddPending,
    onDismissPending: handleDismissPending,
    onDismissAllPending: handleDismissAllPending,
    publishSnack,
    errorSnack,
    journalSavedSnack,
    onClosePublishSnack: handleClosePublishSnack,
    onCloseErrorSnack: handleCloseErrorSnack,
    onCloseJournalSavedSnack: handleCloseJournalSavedSnack,
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <TokenPromptDialog
        open={promptState !== null}
        tokens={promptState?.tokens ?? []}
        originalText={promptState?.originalText ?? ''}
        onSubmit={handleTokenSubmit}
        onCancel={handleTokenCancel}
      />
      {isMobile ? (
        <MobileApp
          {...sharedProps}
          effectiveCallsign={effectiveCallsign}
        />
      ) : (
        <DesktopApp
          {...sharedProps}
          stationStatus={stationStatus}
          filterProfanity={filterProfanity}
          fuzzyCallsign={fuzzyCallsign}
          inputDevice={inputDevice}
          systemMonitorSink={systemMonitorSink}
          inputDevices={inputDevices}
          monitorSinks={monitorSinks}
          outputDevice={outputDevice}
          outputDevices={outputDevices}
          spectroColormap={spectroColormap}
          spectroFreqRange={spectroFreqRange}
          spectroTimeWindowS={spectroTimeWindowS}
          onToggleProfanity={handleToggleProfanity}
          onToggleFuzzy={handleToggleFuzzy}
          onInputDeviceChange={handleInputDeviceChange}
          onOutputDeviceChange={handleOutputDeviceChange}
          onSpectroColormapChange={handleSpectroColormapChange}
          onSpectroFreqRangeChange={handleSpectroFreqRangeChange}
          onSpectroTimeWindowChange={handleSpectroTimeWindowChange}
          showWaterfall={showWaterfall}
          onToggleWaterfall={handleToggleWaterfall}
          showAttendance={showAttendance}
          showJournal={showJournal}
          showNcs={showNcs}
          panelOrder={panelOrder}
          onToggleAttendance={handleToggleAttendance}
          onToggleJournal={handleToggleJournal}
          onToggleContacts={handleToggleContacts}
          onToggleNcs={handleToggleNcs}
          onPanelDragEnd={handlePanelDragEnd}
          onPanelMove={handlePanelMove}
          onClearChat={handleClearChat}
          spectroRef={spectroRef}
        />
      )}
    </ThemeProvider>
  );
}
