import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import { makeTheme, withTouchDensity } from './theme';
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
  StoredStreamMsg,
  PluginManifest,
  FamilyPresenceEntry,
  FamilyStatusPayload,
  SetFamilyReminderPayload,
  SetRolePayload,
  SetUserQuickMessagesPayload,
  NeighborhoodStateMsg,
  IncidentEntry,
  NeighborhoodAlertMsg,
  NeighborhoodCheckinPayload,
  NeighborhoodStatusPayload,
  NeighborhoodStartPayload,
  NeighborhoodEndPayload,
  NeighborhoodCallNextPayload,
  NeighborhoodCallResetPayload,
  NeighborhoodIncidentReportPayload,
  NeighborhoodStreetAlertPayload,
  SetNeighborhoodCoordinatorPayload,
  DeviceTokenRecord,
} from './types/ws';
import type { ChatEntry } from './components/ChatDisplay/ChatDisplay';
import type { SpectrogramHandle } from './components/Spectrogram/Spectrogram';
import type { AudioLevelMeterHandle } from './components/AudioLevelMeter/AudioLevelMeter';
import type { ServerConfig, ServerConfigSaveValues } from './components/ServerConfigPanel/ServerConfigPanel';
import { resolveTxComposition, isPluginEnabled } from './plugins';
import { LoginScreen } from './components/LoginScreen/LoginScreen';
import { SetupScreen } from './components/SetupScreen/SetupScreen';
import { DesktopApp } from './components/DesktopApp/DesktopApp';
import { MobileApp } from './components/MobileApp/MobileApp';
import { AACApp } from './components/AACApp/AACApp';
import { HomeScreen } from './components/HomeScreen/HomeScreen';
import { FamilyPanel } from './components/FamilyPanel/FamilyPanel';
import { NeighborhoodPanel } from './components/NeighborhoodPanel/NeighborhoodPanel';
import { makeDefaultGrid, sanitizeAacGrid } from './components/AACApp/defaultGrid';
import { SettingsDialog } from './components/SettingsDialog/SettingsDialog';
import { CalibrationDialog } from './components/CalibrationDialog/CalibrationDialog';
import { UsersPanel } from './components/UsersPanel/UsersPanel';
import { DEFAULTS as QUICK_DEFAULTS } from './components/QuickMessages/QuickMessages';
import { newlyMissed } from './family/presence';
import { useDeviceClass } from './hooks/useDeviceClass';
import { ScreenFlash, VIBRATE_PATTERNS, type FlashKind } from './components/ScreenFlash/ScreenFlash';
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

// Map one backfilled stream message (chat_history) to a ChatEntry. Mirrors the
// live tx_echo / chat_echo / rx_message-final handlers, minus their live side
// effects (notifications, partial bookkeeping) — history holds finals only.
export function streamMsgToEntry(msg: StoredStreamMsg): ChatEntry {
  if (msg.type === 'tx_echo') {
    const recipient =
      msg.target_call && msg.target_call !== 'ALL'
        ? msg.target_name
          ? `${msg.target_call} — ${msg.target_name}`
          : msg.target_call
        : undefined;
    return {
      id: nextId(),
      timestamp: formatTime(msg.ts),
      kind: 'tx',
      sender: msg.display_name || msg.operator || msg.callsign,
      recipient,
      text: msg.text,
    };
  }
  if (msg.type === 'chat_echo') {
    return {
      id: nextId(),
      timestamp: formatTime(msg.ts),
      kind: 'chat',
      sender: msg.display_name || msg.operator || msg.callsign,
      text: msg.text,
    };
  }
  // rx_message
  return {
    id: nextId(),
    timestamp: formatTime(msg.ts),
    kind: 'rx',
    sender: msg.from || msg.callsign || undefined,
    text: msg.text,
    callsign_spans: msg.callsign_spans,
    source: msg.source,
  };
}

import type { JournalResultDraft, PendingStation, PromptState } from './types/appTypes';
import type { AACGrid } from './types/aac';
import { TokenPromptDialog } from './components/TokenPromptDialog/TokenPromptDialog';
import { ShortcutOverlay } from './components/ShortcutOverlay/ShortcutOverlay';
import { ConfirmDialog } from './components/ConfirmDialog';

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
  const levelMeterRef = useRef<AudioLevelMeterHandle>(null);
  const profileRef = useRef(profile);
  profileRef.current = profile;
  const pendingTranscriptRef = useRef<string>('');

  // Panel visibility
  const [showAttendance, setShowAttendance] = useState(false);
  const [showJournal, setShowJournal] = useState(false);
  const [showContacts, setShowContacts] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showCalibration, setShowCalibration] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  // Home-screen shell: which activity is in front (desktop only). Chat unread
  // count is the simplest honest Phase 1 measure — messages received while on home.
  const [activity, setActivity] = useState<'home' | 'station' | 'family' | 'neighborhood'>('home');
  const homeSeenCountRef = useRef(0);

  // Family activity: presence roster (last_heard/last_ok/missed_checkin per
  // family member) and check-in reminders (admin-configured, hidden from kids).
  const [familyPresence, setFamilyPresence] = useState<FamilyPresenceEntry[]>([]);
  const [familyReminders, setFamilyReminders] = useState<Record<string, { time: string; enabled: boolean }>>({});

  // Neighborhood activity: net state (roster + round-table current call),
  // the incident feed, street-alert banner history (last 3, deduped by id),
  // and the most recent incident-report validation error from the server.
  const [neighborhoodState, setNeighborhoodState] = useState<NeighborhoodStateMsg | null>(null);
  const [incidents, setIncidents] = useState<IncidentEntry[]>([]);
  const [neighborhoodAlerts, setNeighborhoodAlerts] = useState<NeighborhoodAlertMsg[]>([]);
  const [incidentError, setIncidentError] = useState<string | null>(null);
  const [serverConfig, setServerConfig] = useState<ServerConfig>({
    vadThreshold: 0.5,
    whisperModel: 'small.en',
    whisperModelFinal: '',
    gainMode: 'agc',
    whisperModelFinalResolved: '',
    squelchAdaptive: false,
    noiseProfile: false,
    sttDebugCapture: false,
    txConditioning: false,
    voxPrimerEnabled: false,
    voxPrimerMs: 300,
    voxPrimerWordEnabled: false,
    voxPrimerWord: 'transmit',
    pttMode: 'manual',
    pttSerialPort: '',
    pttSerialLine: 'RTS',
    monitorPassthrough: false,
    attendanceEnabled: false,
    savedPhrases: [],
  });
  const [plugins, setPlugins] = useState<PluginManifest[]>([]);
  const [pluginBusy, setPluginBusy] = useState(false);
  const [pluginToUninstall, setPluginToUninstall] = useState<string | null>(null);

  // Kiosk wall-display device tokens (admin-managed via SettingsDialog/AdminPanel).
  const [deviceTokens, setDeviceTokens] = useState<DeviceTokenRecord[]>([]);
  // Holds the one-time token immediately after creation; cleared when the
  // settings dialog closes so it never lingers once the admin navigates away.
  const [createdToken, setCreatedToken] = useState<DeviceTokenRecord | null>(null);

  // Dark mode — initialized from localStorage to avoid FOUC; overridden by profile on load
  const [darkMode, setDarkMode] = useState(
    () => localStorage.getItem('radio_tty_dark_mode') === 'true'
  );

  // Waterfall visibility — persisted locally; defaults to visible
  const [showWaterfall, setShowWaterfall] = useState(
    () => localStorage.getItem('radio_tty_show_waterfall') !== 'false'
  );

  // RX audio level meter visibility — persisted locally; defaults to visible
  const [showLevelMeter, setShowLevelMeter] = useState(
    () => localStorage.getItem('radio_tty_show_level_meter') !== 'false'
  );

  // AAC mode — initialized from localStorage so a reload lands straight on the
  // AAC screen (no normal-UI flash); overridden by profile prefs on load
  const [aacMode, setAacMode] = useState(
    () => localStorage.getItem('radio_tty_aac_mode') === 'true'
  );
  const [aacGrid, setAacGrid] = useState<AACGrid | null>(null);
  // Stable fallback grid — regenerating per render would churn button ids.
  const defaultAacGrid = useMemo(() => makeDefaultGrid(), []);

  // Interface tier ("simple" hides advanced controls) — persisted locally;
  // overridden by profile prefs on load
  const [uiLevel, setUiLevel] = useState<'simple' | 'operator'>(
    () => (localStorage.getItem('radio_tty_ui_level') as 'simple' | 'operator' | null) ?? 'simple'
  );

  // Text size scale — persisted locally; overridden by profile prefs on load
  const [fontScale, setFontScale] = useState(
    () => Number(localStorage.getItem('radio_tty_font_scale')) || 1
  );

  // High contrast theme — persisted locally; overridden by profile prefs on load
  const [highContrast, setHighContrast] = useState(
    () => localStorage.getItem('radio_tty_high_contrast') === 'true'
  );

  // Switch scanning (single-switch a11y) — persisted locally; overridden by profile prefs on load
  const [switchScan, setSwitchScan] = useState(localStorage.getItem('radio_tty_switch_scan') === 'true');
  const [switchScanIntervalS, setSwitchScanIntervalS] = useState(() => {
    const v = Number(localStorage.getItem('radio_tty_switch_scan_interval_s'));
    return [1, 1.5, 2, 3].includes(v) ? v : 1.5;
  });
  const [visualAlerts, setVisualAlerts] = useState(localStorage.getItem('radio_tty_visual_alerts') === 'true');

  const deviceClass = useDeviceClass();
  const isMobile = deviceClass === 'phone';

  // "?" opens the shortcut overlay anywhere except while typing.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== '?' || e.defaultPrevented) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      setShortcutsOpen((v) => !v);
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const baseTheme = useMemo(
    () => makeTheme(darkMode, { fontScale, highContrast }),
    [darkMode, fontScale, highContrast],
  );
  const theme = useMemo(
    () => (deviceClass === 'tablet' || aacMode ? withTouchDensity(baseTheme) : baseTheme),
    [baseTheme, deviceClass, aacMode],
  );

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
  const [vocabSnack, setVocabSnack] = useState<string | null>(null);
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
  const visualAlertsRef = useRef(false);
  visualAlertsRef.current = visualAlerts;
  const [flash, setFlash] = useState<{ kind: FlashKind; seq: number } | null>(null);
  const [filterProfanity, setFilterProfanity] = useState(true);
  const [spectroColormap, setSpectroColormap] = useState<'viridis' | 'grayscale'>('viridis');
  const [spectroTimeWindowS, setSpectroTimeWindowS] = useState(30);

  // Available TTS voices (sent by server on connect)
  const [voices, setVoices] = useState<VoiceOption[]>([]);

  // Station-wide settings (synced from status message)
  const [sttListening, setSttListening] = useState(true);
  const [serviceMode, setServiceMode] = useState('GMRS');
  const [fuzzyCallsign, setFuzzyCallsign] = useState(false);
  const [fuzzyCallsignRewrite, setFuzzyCallsignRewrite] = useState(false);
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
    ncsPreambleText: '',
    ncsClosingText: '',
    rxMode: 'voice',
    display_quick_messages: [] as string[],
  });

  // Plugin infrastructure — last WS message forwarded to mounted plugin panels
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const [channelClear, setChannelClear] = useState(true);

  // NCS panel visibility (admin-only toggle)
  const [showNcs, setShowNcs] = useState(false);

  function triggerVisualAlert(kind: FlashKind) {
    if (!visualAlertsRef.current) return;
    setFlash((prev) => ({ kind, seq: (prev?.seq ?? 0) + 1 }));
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
      navigator.vibrate(VIBRATE_PATTERNS[kind]);
    }
  }

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
          triggerVisualAlert('rx');
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
        if (msg.fuzzy_callsign_rewrite !== undefined) setFuzzyCallsignRewrite(msg.fuzzy_callsign_rewrite);
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
          ncsPreambleText: msg.ncs_preamble_text ?? prev.ncsPreambleText,
          ncsClosingText: msg.ncs_closing_text ?? prev.ncsClosingText,
          rxMode: msg.rx_mode ?? prev.rxMode,
          display_quick_messages: msg.display_quick_messages ?? prev.display_quick_messages,
        }));
        setServerConfig((prev) => ({
          vadThreshold: msg.vad_threshold ?? prev.vadThreshold,
          whisperModel: msg.whisper_model ?? prev.whisperModel,
          whisperModelFinal: msg.whisper_model_final ?? prev.whisperModelFinal,
          gainMode: msg.stt_gain_mode ?? prev.gainMode,
          whisperModelFinalResolved: msg.whisper_model_final_resolved ?? prev.whisperModelFinalResolved,
          squelchAdaptive: msg.squelch_adaptive ?? prev.squelchAdaptive,
          noiseProfile: msg.stt_noise_profile ?? prev.noiseProfile,
          sttDebugCapture: msg.stt_debug_capture ?? prev.sttDebugCapture,
          txConditioning: msg.tx_conditioning ?? prev.txConditioning,
          voxPrimerEnabled: msg.vox_primer_enabled ?? prev.voxPrimerEnabled,
          voxPrimerMs: msg.vox_primer_ms ?? prev.voxPrimerMs,
          voxPrimerWordEnabled: msg.vox_primer_word_enabled ?? prev.voxPrimerWordEnabled,
          voxPrimerWord: msg.vox_primer_word ?? prev.voxPrimerWord,
          pttMode: msg.ptt_mode ?? prev.pttMode,
          pttSerialPort: msg.ptt_serial_port ?? prev.pttSerialPort,
          pttSerialLine: msg.ptt_serial_line ?? prev.pttSerialLine,
          monitorPassthrough: msg.monitor_passthrough ?? prev.monitorPassthrough,
          attendanceEnabled: msg.attendance_enabled ?? prev.attendanceEnabled,
          savedPhrases: msg.saved_phrases ?? prev.savedPhrases,
        }));
        if (msg.plugins) setPlugins(msg.plugins);
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
        if (prefs.filter_profanity !== undefined) setFilterProfanity(prefs.filter_profanity);
        if (prefs.listen_only !== undefined) setListenOnly(prefs.listen_only);
        if (prefs.read_aloud !== undefined) setReadAloud(prefs.read_aloud);
        if (prefs.notifications_enabled !== undefined) setNotificationsEnabled(prefs.notifications_enabled);
        if (prefs.spectro_colormap) setSpectroColormap(prefs.spectro_colormap);
        if (prefs.spectro_time_window_s) setSpectroTimeWindowS(prefs.spectro_time_window_s);
        if (prefs.aac_mode !== undefined) {
          setAacMode(prefs.aac_mode);
          localStorage.setItem('radio_tty_aac_mode', String(prefs.aac_mode));
        }
        if (prefs.aac_grid !== undefined && prefs.aac_grid !== null) {
          setAacGrid(sanitizeAacGrid(prefs.aac_grid));
        }
        if (prefs.ui_level) {
          setUiLevel(prefs.ui_level);
          localStorage.setItem('radio_tty_ui_level', prefs.ui_level);
        }
        if (prefs.font_scale) {
          setFontScale(prefs.font_scale);
          localStorage.setItem('radio_tty_font_scale', String(prefs.font_scale));
        }
        if (prefs.high_contrast !== undefined) {
          setHighContrast(prefs.high_contrast);
          localStorage.setItem('radio_tty_high_contrast', String(prefs.high_contrast));
        }
        if (prefs.switch_scan !== undefined) {
          setSwitchScan(prefs.switch_scan);
          localStorage.setItem('radio_tty_switch_scan', String(prefs.switch_scan));
        }
        if (prefs.switch_scan_interval_s !== undefined) {
          setSwitchScanIntervalS(prefs.switch_scan_interval_s);
          localStorage.setItem('radio_tty_switch_scan_interval_s', String(prefs.switch_scan_interval_s));
        }
        if (prefs.visual_alerts !== undefined) {
          setVisualAlerts(prefs.visual_alerts);
          localStorage.setItem('radio_tty_visual_alerts', String(prefs.visual_alerts));
        }
        // One-time migration: the QuickMessages panel used to keep its presets
        // purely in localStorage. Once the server-side pref exists this is a
        // no-op forever (prefs.quick_messages stops being undefined once the
        // save below round-trips) — so no extra "have we migrated" flag needed.
        if (prefs.quick_messages === undefined) {
          const raw = localStorage.getItem('radio_tty_quick_messages');
          if (raw) {
            try {
              const parsed = JSON.parse(raw);
              if (
                Array.isArray(parsed) &&
                parsed.length > 0 &&
                JSON.stringify(parsed) !== JSON.stringify(QUICK_DEFAULTS)
              ) {
                sendRef.current({ type: 'save_user_prefs', prefs: { quick_messages: parsed } });
              }
            } catch {
              // malformed localStorage — nothing to migrate
            }
          }
        }
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

      case 'chat_history': {
        // Backfill of the shared stream since the last clear. Replaces the
        // local log (sent once on connect, before any live messages).
        const entries = msg.messages.map(streamMsgToEntry);
        setMessages(entries);
        // Treat backfilled history as already seen so the Home unread badge
        // only counts messages that arrive after login, not the whole log.
        homeSeenCountRef.current = entries.length;
        break;
      }

      case 'chat_cleared':
        // An admin cleared the chat for everyone. Reset the seen-count
        // ref alongside the message list — otherwise it stays ahead of
        // the now-empty log and the Home unread badge math
        // (messages.length - homeSeenCountRef.current) goes negative
        // (clamped to 0, but stays wrong) until enough new messages
        // arrive to catch back up.
        setMessages([]);
        homeSeenCountRef.current = 0;
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
        levelMeterRef.current?.pushRow(msg.row);
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
        triggerVisualAlert('weather');
        break;

      case 'family_presence': {
        const entries = msg.entries;
        setFamilyPresence((prev) => {
          if (
            notificationsEnabledRef.current &&
            Notification.permission === 'granted' &&
            document.visibilityState === 'hidden'
          ) {
            for (const member of newlyMissed(prev, entries)) {
              new Notification(`⚠️ ${member.display_name}`, {
                body: 'Missed check-in',
                tag: `family-missed-${member.user_id}`,
                silent: false,
              });
            }
          }
          if (newlyMissed(prev, entries).length > 0) triggerVisualAlert('family');
          return entries;
        });
        break;
      }

      case 'family_reminders':
        setFamilyReminders(msg.reminders);
        break;

      case 'neighborhood_state':
        setNeighborhoodState(msg);
        break;

      case 'device_tokens':
        setDeviceTokens(msg.tokens);
        break;

      case 'device_token_created':
        setCreatedToken(msg.record);
        break;

      case 'neighborhood_incidents':
        setIncidents(msg.incidents);
        break;

      case 'neighborhood_alert':
        setNeighborhoodAlerts((prev) => {
          if (prev.some((a) => a.id === msg.id)) return prev;
          if (
            notificationsEnabledRef.current &&
            Notification.permission === 'granted' &&
            document.visibilityState === 'hidden'
          ) {
            new Notification('📢 Neighborhood Alert', {
              body: msg.message.slice(0, 120),
              tag: `neighborhood-alert-${msg.id}`,
              silent: false,
            });
          }
          triggerVisualAlert('street');
          return [msg, ...prev].slice(0, 3);
        });
        break;

      case 'neighborhood_incident_sent':
        setIncidentError(null);
        break;

      case 'neighborhood_incident_error':
        setIncidentError(msg.detail);
        break;

      case 'neighborhood_journal_saved':
        setJournalSavedSnack('Neighborhood net journal saved');
        sendRef.current({ type: 'list_journals' });
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

      case 'vocabulary_rescanned':
        setVocabSnack(`Biasing ${msg.term_count} terms (${msg.callsign_count} callsigns).`);
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

  function handleToggleFuzzyRewrite() {
    send({ type: 'set_config', fuzzy_callsign_rewrite: !fuzzyCallsignRewrite });
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
    display_quick_messages: string[];
  }) {
    send({ type: 'set_admin_config', ...values });
  }

  function handleServerConfigSave(values: ServerConfigSaveValues) {
    send({ type: 'set_server_config', ...values });
  }

  function handlePluginsSave(draft: Record<string, Record<string, unknown>>) {
    // Plugin enable + config drafts ride the server-config channel under a
    // `plugins` namespace; the backend coerces values against each plugin's
    // schema and enforces mutual exclusion (resolve_conflicts).
    send({ type: 'set_server_config', plugins: draft });
  }

  function authHeaders(): Record<string, string> {
    const t = localStorage.getItem('auth_token');
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  async function handleInstallPlugin(file: File) {
    setPluginBusy(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/plugins/install', { method: 'POST', body: form, headers: authHeaders() });
      if (!res.ok) {
        const detail = await res.text();
        window.alert(`Install failed: ${detail || res.status}`);
      }
    } catch (err) {
      window.alert(`Install failed: ${err}`);
    } finally {
      setPluginBusy(false);
    }
  }

  async function handleReloadPlugin(id: string) {
    setPluginBusy(true);
    try {
      await fetch(`/plugins/${encodeURIComponent(id)}/reload`, { method: 'POST', headers: authHeaders() });
    } finally {
      setPluginBusy(false);
    }
  }

  function handleUninstallPlugin(id: string) {
    setPluginToUninstall(id);
  }

  async function confirmUninstallPlugin() {
    const id = pluginToUninstall;
    if (!id) return;
    setPluginBusy(true);
    try {
      await fetch(`/plugins/${encodeURIComponent(id)}`, { method: 'DELETE', headers: authHeaders() });
    } finally {
      setPluginBusy(false);
    }
  }

  function handleRescanVocabulary() {
    send({ type: 'rescan_vocabulary' });
  }

  // Family activity — "I'm OK" check-in and admin management sends.
  function sendImOk() {
    send({ type: 'family_status', status: 'ok' } satisfies FamilyStatusPayload);
  }

  function sendSetReminder(userId: string, time: string | null, enabled: boolean) {
    send({ type: 'set_family_reminder', user_id: userId, time, enabled } satisfies SetFamilyReminderPayload);
  }

  function sendSetRole(userId: string, role: 'admin' | 'adult' | 'kid') {
    send({ type: 'set_role', user_id: userId, role } satisfies SetRolePayload);
  }

  function sendSetUserQuickMessages(userId: string, list: string[]) {
    send({
      type: 'set_user_quick_messages',
      user_id: userId,
      quick_messages: list,
    } satisfies SetUserQuickMessagesPayload);
  }

  // Neighborhood activity — check-in/status/round-table/incident/alert sends.
  function sendNeighborhoodCheckin() {
    send({ type: 'neighborhood_checkin' } satisfies NeighborhoodCheckinPayload);
  }

  function sendNeighborhoodStatus(status: 'checked_in' | 'standby', userId?: string) {
    send({
      type: 'neighborhood_status',
      status,
      ...(userId ? { user_id: userId } : {}),
    } satisfies NeighborhoodStatusPayload);
  }

  function sendIncidentReport(category: string, description: string, location: string) {
    // Reset before each attempt so a rejection always arrives as a
    // null -> string transition, even when the error text is identical
    // to a previous attempt's.
    setIncidentError(null);
    send({
      type: 'neighborhood_incident_report',
      category,
      description,
      location,
    } satisfies NeighborhoodIncidentReportPayload);
  }

  function sendStreetAlert(message: string) {
    send({ type: 'neighborhood_street_alert', message } satisfies NeighborhoodStreetAlertPayload);
  }

  function sendNeighborhoodStart() {
    send({ type: 'neighborhood_start' } satisfies NeighborhoodStartPayload);
  }

  function sendNeighborhoodEnd() {
    send({ type: 'neighborhood_end' } satisfies NeighborhoodEndPayload);
  }

  function sendNeighborhoodCallNext() {
    send({ type: 'neighborhood_call_next' } satisfies NeighborhoodCallNextPayload);
  }

  function sendNeighborhoodCallReset() {
    send({ type: 'neighborhood_call_reset' } satisfies NeighborhoodCallResetPayload);
  }

  function sendSetNeighborhoodCoordinator(userId: string, coordinator: boolean) {
    send({
      type: 'set_neighborhood_coordinator',
      user_id: userId,
      coordinator,
    } satisfies SetNeighborhoodCoordinatorPayload);
  }

  function handleCreateDeviceToken(label: string) {
    send({ type: 'device_token_create', label });
  }

  function handleRevokeDeviceToken(id: string) {
    send({ type: 'device_token_revoke', id });
  }

  function handleToggleDark() {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem('radio_tty_dark_mode', String(next));
    send({ type: 'save_user_prefs', prefs: { dark_mode: next } });
  }

  function handleUiLevelChange(next: 'simple' | 'operator') {
    setUiLevel(next);
    localStorage.setItem('radio_tty_ui_level', next);
    send({ type: 'save_user_prefs', prefs: { ui_level: next } });
  }

  function handleFontScaleChange(next: number) {
    setFontScale(next);
    localStorage.setItem('radio_tty_font_scale', String(next));
    send({ type: 'save_user_prefs', prefs: { font_scale: next } });
  }

  function handleToggleHighContrast() {
    const next = !highContrast;
    setHighContrast(next);
    localStorage.setItem('radio_tty_high_contrast', String(next));
    send({ type: 'save_user_prefs', prefs: { high_contrast: next } });
  }

  function handleToggleSwitchScan() {
    const next = !switchScan;
    setSwitchScan(next);
    localStorage.setItem('radio_tty_switch_scan', String(next));
    send({ type: 'save_user_prefs', prefs: { switch_scan: next } });
  }

  function handleSwitchScanIntervalChange(next: number) {
    setSwitchScanIntervalS(next);
    localStorage.setItem('radio_tty_switch_scan_interval_s', String(next));
    send({ type: 'save_user_prefs', prefs: { switch_scan_interval_s: next } });
  }

  function handleToggleVisualAlerts() {
    const next = !visualAlerts;
    setVisualAlerts(next);
    localStorage.setItem('radio_tty_visual_alerts', String(next));
    send({ type: 'save_user_prefs', prefs: { visual_alerts: next } });
  }

  function handleToggleAacMode() {
    const next = !aacMode;
    setAacMode(next);
    localStorage.setItem('radio_tty_aac_mode', String(next));
    send({ type: 'save_user_prefs', prefs: { aac_mode: next } });
  }

  function handleSaveAacGrid(grid: AACGrid) {
    setAacGrid(grid);
    send({ type: 'save_user_prefs', prefs: { aac_grid: grid } });
  }

  function handleToggleWaterfall() {
    const next = !showWaterfall;
    setShowWaterfall(next);
    localStorage.setItem('radio_tty_show_waterfall', String(next));
  }

  function handleToggleLevelMeter() {
    const next = !showLevelMeter;
    setShowLevelMeter(next);
    localStorage.setItem('radio_tty_show_level_meter', String(next));
  }

  function handleClearChat() {
    // Admin-only and global: the server wipes the shared stream and broadcasts
    // `chat_cleared`, which clears every client's log (including ours).
    send({ type: 'clear_chat' });
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
  const handleToggleSettings = () => setShowSettings((v) => {
    const next = !v;
    if (next) {
      // Device tokens are admin-only server-side; only ask for the list when
      // the profile is actually admin, mirroring the isAdmin gate used to hide
      // the Station/System tabs below. Non-admins sending this got back a
      // hard "Admin access required." error toast on every Settings open.
      if (profile?.is_admin) {
        send({ type: 'device_token_list' });
      }
    } else {
      setCreatedToken(null);
    }
    return next;
  });
  function handleToggleNcs() {
    setShowNcs((v) => !v);
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
  function handleCloseVocabSnack() { setVocabSnack(null); }
  function handleVerifyAllDismiss() { setVerifyAllComplete(false); }

  function handleGoHome() {
    homeSeenCountRef.current = messages.length;
    setActivity('home');
  }
  function handleOpenActivity(a: 'station' | 'ncs' | 'family' | 'neighborhood') {
    if (a === 'family') {
      setActivity('family');
      return;
    }
    if (a === 'neighborhood') {
      setActivity('neighborhood');
      return;
    }
    if (a === 'ncs') setShowNcs(true);
    setActivity('station');
  }
  const unreadCount = Math.max(0, messages.length - homeSeenCountRef.current);

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

  // Active TX-composition constraint contributed by plugins (e.g. MeshCore caps
  // the message length so the prefixed packet fits one mesh frame).
  const txComposition = resolveTxComposition(plugins, profile);

  // Kid gating: hide Settings entry points and other adult-only affordances.
  const isKid = profile?.role === 'kid';
  // Kids only ever see an admin-curated preset list (server-enforced TX
  // allowlist) — falling back to QUICK_DEFAULTS for a kid with an empty
  // allowlist would show buttons that error on every tap. Adults keep the
  // QUICK_DEFAULTS fallback since their tx_message isn't allowlist-gated.
  const quickMessages = profile?.prefs?.quick_messages ?? (isKid ? [] : QUICK_DEFAULTS);

  // Coordinator gating for the Neighborhood activity — an admin-only grant
  // (see set_neighborhood_coordinator), not a role, so it reads from prefs.
  const isCoordinator = profile?.prefs?.neighborhood_coordinator === true;

  // netDay/netTime are sourced from neighborhood_state, not the status
  // message that feeds the rest of adminConfig — merge them in here so
  // every consumer of adminConfig (AdminPanel via SettingsDialog, MobileApp)
  // sees the same shape.
  const mergedAdminConfig = {
    ...adminConfig,
    netDay: neighborhoodState?.net_day ?? '',
    netTime: neighborhoodState?.net_time ?? '',
  };

  const sharedProps = {
    txComposition,
    familyPresence,
    familyReminders,
    neighborhoodState,
    incidents,
    neighborhoodAlerts,
    incidentError,
    isCoordinator,
    isKid,
    quickMessages,
    sendImOk,
    sendSetReminder,
    sendSetRole,
    sendSetUserQuickMessages,
    sendNeighborhoodCheckin,
    sendNeighborhoodStatus,
    sendIncidentReport,
    sendStreetAlert,
    sendNeighborhoodStart,
    sendNeighborhoodEnd,
    sendNeighborhoodCallNext,
    sendNeighborhoodCallReset,
    sendSetNeighborhoodCoordinator,
    profile: profile!,
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
    uiLevel,
    adminConfig: mergedAdminConfig,
    showSettings,
    onToggleSettings: handleToggleSettings,
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
    vocabSnack,
    onClosePublishSnack: handleClosePublishSnack,
    onCloseErrorSnack: handleCloseErrorSnack,
    onCloseJournalSavedSnack: handleCloseJournalSavedSnack,
    onCloseVocabSnack: handleCloseVocabSnack,
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ScreenFlash flash={flash} />
      <TokenPromptDialog
        open={promptState !== null}
        tokens={promptState?.tokens ?? []}
        originalText={promptState?.originalText ?? ''}
        onSubmit={handleTokenSubmit}
        onCancel={handleTokenCancel}
      />
      <ShortcutOverlay open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      <ConfirmDialog
        open={pluginToUninstall !== null}
        title="Uninstall plugin?"
        body={pluginToUninstall ? `"${pluginToUninstall}" and its files will be removed.` : ''}
        confirmLabel="Yes, uninstall"
        destructive
        switchScan={switchScan}
        switchScanIntervalS={switchScanIntervalS}
        onConfirm={confirmUninstallPlugin}
        onClose={() => setPluginToUninstall(null)}
      />
      {aacMode ? (
        <AACApp
          profile={profile}
          effectiveCallsign={effectiveCallsign}
          connected={connected}
          transmitting={transmitting}
          listenOnly={listenOnly}
          messages={messages}
          grid={aacGrid ?? defaultAacGrid}
          onSend={handleSend}
          onTxAbort={handleTxAbort}
          onSaveGrid={handleSaveAacGrid}
          onExitAac={handleToggleAacMode}
          switchScan={switchScan}
          switchScanIntervalS={switchScanIntervalS}
        />
      ) : isMobile ? (
        <MobileApp
          {...sharedProps}
          effectiveCallsign={effectiveCallsign}
        />
      ) : activity === 'home' ? (
        <HomeScreen
          profile={profile}
          connected={connected}
          uiLevel={uiLevel}
          ncsEnabled={isPluginEnabled(plugins, 'ncs')}
          unreadCount={unreadCount}
          familyEntries={familyPresence}
          neighborhoodActive={neighborhoodState?.active ?? false}
          netDay={neighborhoodState?.net_day ?? ''}
          netTime={neighborhoodState?.net_time ?? ''}
          neighborhoodAlerts={neighborhoodAlerts}
          isKid={isKid}
          onOpenActivity={handleOpenActivity}
          onOpenSettings={handleToggleSettings}
          onLogout={handleLogout}
          switchScan={switchScan && !showSettings}
          switchScanIntervalS={switchScanIntervalS}
        />
      ) : activity === 'family' ? (
        <FamilyPanel
          entries={familyPresence}
          reminders={familyReminders}
          isKid={isKid}
          isAdmin={!!profile.is_admin}
          quickMessages={quickMessages}
          onImOk={sendImOk}
          onQuickMessage={(text) => handleSend(text, '', '')}
          onSetReminder={sendSetReminder}
          onGoHome={handleGoHome}
        />
      ) : activity === 'neighborhood' ? (
        <NeighborhoodPanel
          roster={neighborhoodState?.roster ?? []}
          netActive={neighborhoodState?.active ?? false}
          currentCall={neighborhoodState?.current_call ?? null}
          incidents={incidents}
          alerts={neighborhoodAlerts}
          netDay={neighborhoodState?.net_day ?? ''}
          netTime={neighborhoodState?.net_time ?? ''}
          isCoordinator={isCoordinator}
          isKid={isKid}
          myUserId={profile.id}
          onCheckin={sendNeighborhoodCheckin}
          onStatusChange={(status) => sendNeighborhoodStatus(status)}
          onIncidentReport={({ category, description, location }) => sendIncidentReport(category, description, location)}
          incidentError={incidentError}
          onStreetAlert={sendStreetAlert}
          onStartNet={sendNeighborhoodStart}
          onEndNet={sendNeighborhoodEnd}
          onCallNext={sendNeighborhoodCallNext}
          onNewRound={sendNeighborhoodCallReset}
          onGoHome={handleGoHome}
        />
      ) : (
        <DesktopApp
          {...sharedProps}
          onGoHome={handleGoHome}
          stationStatus={stationStatus}
          spectroColormap={spectroColormap}
          spectroTimeWindowS={spectroTimeWindowS}
          showWaterfall={showWaterfall}
          onToggleWaterfall={handleToggleWaterfall}
          showLevelMeter={showLevelMeter}
          onToggleLevelMeter={handleToggleLevelMeter}
          showAttendance={showAttendance}
          showJournal={showJournal}
          showNcs={showNcs}
          ncsEnabled={isPluginEnabled(plugins, 'ncs')}
          onToggleAttendance={handleToggleAttendance}
          onToggleJournal={handleToggleJournal}
          onToggleContacts={handleToggleContacts}
          onToggleNcs={handleToggleNcs}
          onClearChat={handleClearChat}
          spectroRef={spectroRef}
          levelMeterRef={levelMeterRef}
        />
      )}
      {/* isAdmin is UX-only gating (hides Station/System tabs). Server enforces
          admin authorization on set_admin_config / set_server_config. */}
      <SettingsDialog
        open={showSettings}
        onClose={handleToggleSettings}
        isAdmin={!!profile?.is_admin}
        filterProfanity={filterProfanity}
        aacMode={aacMode}
        onToggleAacMode={handleToggleAacMode}
        fuzzyCallsign={fuzzyCallsign}
        fuzzyCallsignRewrite={fuzzyCallsignRewrite}
        inputDevice={inputDevice}
        systemMonitorSink={systemMonitorSink}
        inputDevices={inputDevices}
        monitorSinks={monitorSinks}
        outputDevice={outputDevice}
        outputDevices={outputDevices}
        spectroColormap={spectroColormap}
        spectroFreqRange={spectroFreqRange}
        spectroTimeWindowS={spectroTimeWindowS}
        uiLevel={uiLevel}
        fontScale={fontScale}
        highContrast={highContrast}
        onToggleProfanity={handleToggleProfanity}
        onToggleFuzzy={handleToggleFuzzy}
        onToggleFuzzyRewrite={handleToggleFuzzyRewrite}
        onInputDeviceChange={handleInputDeviceChange}
        onOutputDeviceChange={handleOutputDeviceChange}
        onSpectroColormapChange={handleSpectroColormapChange}
        onSpectroFreqRangeChange={handleSpectroFreqRangeChange}
        onSpectroTimeWindowChange={handleSpectroTimeWindowChange}
        onUiLevelChange={handleUiLevelChange}
        onFontScaleChange={handleFontScaleChange}
        onToggleHighContrast={handleToggleHighContrast}
        switchScan={switchScan}
        switchScanIntervalS={switchScanIntervalS}
        visualAlerts={visualAlerts}
        onToggleSwitchScan={handleToggleSwitchScan}
        onSwitchScanIntervalChange={handleSwitchScanIntervalChange}
        onToggleVisualAlerts={handleToggleVisualAlerts}
        adminConfig={mergedAdminConfig}
        voices={voices}
        voicePreviewBusy={voicePreviewBusy}
        onAdminSave={handleAdminSave}
        onPreviewVoice={handlePreviewVoice}
        deviceTokens={deviceTokens}
        createdToken={createdToken}
        onCreateDeviceToken={handleCreateDeviceToken}
        onRevokeDeviceToken={handleRevokeDeviceToken}
        serverConfig={serverConfig}
        onServerConfigSave={handleServerConfigSave}
        onRescanVocabulary={handleRescanVocabulary}
        onOpenCalibration={() => setShowCalibration(true)}
        plugins={plugins}
        onPluginsSave={handlePluginsSave}
        onInstallPlugin={handleInstallPlugin}
        onReloadPlugin={handleReloadPlugin}
        onUninstallPlugin={handleUninstallPlugin}
        pluginBusy={pluginBusy}
        usersPanel={profile?.is_admin && (
          <UsersPanel
            profiles={profiles}
            currentUserId={profile.id}
            onCreateProfile={(data) => send({ type: 'create_profile', ...data })}
            onDeleteProfile={(userId) => send({ type: 'delete_profile', user_id: userId })}
            onResetLockout={(userId) => send({ type: 'reset_lockout', user_id: userId })}
            onSetRole={sendSetRole}
            onSetUserQuickMessages={sendSetUserQuickMessages}
            onSetNeighborhoodCoordinator={sendSetNeighborhoodCoordinator}
          />
        )}
      />
      <CalibrationDialog
        open={showCalibration}
        onClose={() => setShowCalibration(false)}
        send={send}
        lastMessage={lastMessage}
      />
    </ThemeProvider>
  );
}
