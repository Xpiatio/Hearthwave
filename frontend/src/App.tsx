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
import { NCSPanel } from './components/NCSPanel/NCSPanel';
import { Spectrogram } from './components/Spectrogram/Spectrogram';
import type { SpectrogramHandle } from './components/Spectrogram/Spectrogram';
import { QuickMessages } from './components/QuickMessages/QuickMessages';
import { ContactsDialog } from './components/ContactsDialog/ContactsDialog';
import { PendingStationsBar } from './components/PendingStationsBar/PendingStationsBar';
import { ConfigPanel } from './components/ConfigPanel/ConfigPanel';
import { AdminPanel } from './components/AdminPanel/AdminPanel';
import { ServerConfigPanel } from './components/ServerConfigPanel/ServerConfigPanel';
import type { ServerConfig } from './components/ServerConfigPanel/ServerConfigPanel';
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
  const recentFinalIdsRef = useRef<Map<string, string>>(new Map());
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
  const [showServerConfig, setShowServerConfig] = useState(false);
  const [serverConfig, setServerConfig] = useState<ServerConfig>({
    vadThreshold: 0.5,
    whisperModel: 'small.en',
    pttMode: 'manual',
    pttSerialPort: '',
    pttSerialLine: 'RTS',
    monitorPassthrough: false,
    attendanceEnabled: false,
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
  const [voicePreviewBusy, setVoicePreviewBusy] = useState(false);

  // FCC / Callsigns
  const [pendingStations, setPendingStations] = useState<PendingStation[]>([]);
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [fccLookupResult, setFccLookupResult] = useState<FccLookupResultMsg | null>(null);
  const [verifyAllComplete, setVerifyAllComplete] = useState(false);
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
          const speaker = speakerLabel(msg.speaker_callsign, msg.speaker_name, msg.cluster_label);
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
                      speaker,
                      cluster_label: msg.cluster_label,
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
                speaker,
                cluster_label: msg.cluster_label,
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
          pttMode: msg.ptt_mode ?? prev.pttMode,
          pttSerialPort: msg.ptt_serial_port ?? prev.pttSerialPort,
          pttSerialLine: msg.ptt_serial_line ?? prev.pttSerialLine,
          monitorPassthrough: msg.monitor_passthrough ?? prev.monitorPassthrough,
          attendanceEnabled: msg.attendance_enabled ?? prev.attendanceEnabled,
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

      case 'voice_preview_audio':
      case 'tx_audio':
      case 'rx_audio': {
        // Decode base64 int16 PCM and play in the browser via Web Audio API.
        // tx_audio routes transmitted speech through the local audio output
        // (e.g. 3.5mm jack to radio); voice_preview_audio does the same for previews.
        // rx_audio plays incoming RX transcripts aloud (read_aloud pref).
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
          src.onended = () => ctx.close();
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

  function handleServerConfigSave(values: {
    vad_threshold: number;
    whisper_model: string;
    ptt_mode: string;
    ptt_serial_port: string;
    ptt_serial_line: string;
    monitor_passthrough: boolean;
    attendance_enabled: boolean;
  }) {
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
          readAloud={readAloud}
          onToggleReadAloud={handleToggleReadAloud}
          notificationsEnabled={notificationsEnabled}
          onToggleNotifications={handleToggleNotifications}
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
          showServerConfig={showServerConfig}
          onToggleServerConfig={() => setShowServerConfig((v) => !v)}
          showNcs={showNcs}
          onToggleNcs={() => {
            const next = !showNcs;
            setShowNcs(next);
            setPanelOrder((prev) =>
              next && !prev.includes('ncs') ? [...prev, 'ncs'] : prev.filter((id) => id !== 'ncs' || next)
            );
          }}
          showWaterfall={showWaterfall}
          onToggleWaterfall={handleToggleWaterfall}
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
          voicePreviewBusy={voicePreviewBusy}
          onPreviewVoice={handlePreviewVoice}
          stationLengthScale={adminConfig.stationLengthScale}
          onSaveTtsPrefs={handleSaveTtsPrefs}
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
              if (id === 'ncs' && showNcs) {
                return (
                  <DraggablePanel key="ncs" id="ncs">
                    <NCSPanel
                      send={send}
                      lastMessage={lastMessage}
                      contacts={contacts}
                      channelClear={channelClear}
                      transmitting={transmitting}
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

        <Box sx={{ display: 'flex', flexDirection: 'row', flex: '1 1 auto', overflow: 'hidden' }}>
          {showWaterfall && (
            <Spectrogram
              ref={spectroRef}
              colormap={spectroColormap}
              timeWindowS={spectroTimeWindowS}
            />
          )}
          <ChatDisplay
            entries={messages}
            contacts={contacts}
            showCallsignChips={showCallsignChips}
            onEnrollCluster={handleEnrollCluster}
          />
        </Box>

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
          prefilledName={pendingPrefilledName}
          prefilledLocation={pendingPrefilledLocation}
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
          voicePreviewBusy={voicePreviewBusy}
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

        <ServerConfigPanel
          open={showServerConfig}
          onClose={() => setShowServerConfig(false)}
          config={serverConfig}
          onSave={handleServerConfigSave}
        />

        <Snackbar
          open={publishSnack !== null}
          autoHideDuration={5000}
          onClose={() => setPublishSnack(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert onClose={() => setPublishSnack(null)} severity="success" sx={{ width: '100%' }}>
            {publishSnack}
          </Alert>
        </Snackbar>

        <Snackbar
          open={errorSnack !== null}
          autoHideDuration={7000}
          onClose={() => setErrorSnack(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert onClose={() => setErrorSnack(null)} severity="error" sx={{ width: '100%' }}>
            {errorSnack}
          </Alert>
        </Snackbar>
      </Box>
    </ThemeProvider>
  );
}
