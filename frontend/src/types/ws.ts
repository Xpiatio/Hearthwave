import type { AACGrid } from './aac';

// [start, end, canonical_callsign, original_heard_text?] — the 4th element is
// present (non-null) only when fuzzy_callsign_rewrite corrected the transcript.
export type CallsignSpan =
  | [number, number, string]
  | [number, number, string, string | null];

export interface Contact {
  callsign: string;
  name?: string;
  location?: string;
  gmrs_callsign?: string;
  ham_callsign?: string;
  verified?: boolean;
  verified_at?: string;
  fcc_name?: string;
  fcc_location?: string;
}

export interface RxMessageMsg {
  type: 'rx_message';
  ts: string;
  from: string;
  callsign: string;
  text: string;
  utterance_id: string;
  partial: boolean;
  // [start, end, canonical_callsign] tuples computed by the backend.
  // Spans reference original character positions in `text`, handling NATO-phonetic,
  // spaced, hyphenated, and compact callsign forms.
  callsign_spans?: CallsignSpan[];
  source?: 'voice' | 'cw';
}

export interface RxMessagePatchMsg {
  type: 'rx_message_patch';
  utterance_id: string;
  callsign_spans: CallsignSpan[];
}

export interface StatusMsg {
  type: 'status';
  radio_connected: boolean;
  volume_ok: boolean;
  channel_clear: boolean;
  monitor_enabled?: boolean;
  listen_only?: boolean;
  stt_listening?: boolean;
  service_mode?: string;
  filter_profanity?: boolean;
  fuzzy_callsign?: boolean;
  fuzzy_callsign_rewrite?: boolean;
  spectro_colormap?: 'viridis' | 'grayscale';
  spectro_freq_range?: 'voice' | 'full';
  spectro_time_window_s?: number;
  input_device?: string | number;
  output_device?: string | number;
  system_monitor_sink?: string;
  // Admin-editable identity fields
  station_callsign?: string;
  station_name?: string;
  station_location?: string;
  station_voice?: string;
  station_length_scale?: number;
  gemini_api_key_set?: boolean;
  journals_dir?: string;
  ncs_zone?: string;
  ncs_preamble_text?: string;
  ncs_closing_text?: string;
  rx_mode?: string;
  vad_threshold?: number;
  whisper_model?: string;
  whisper_model_final?: string;
  whisper_model_final_resolved?: string;
  stt_gain_mode?: string;
  squelch_adaptive?: boolean;
  stt_noise_profile?: boolean;
  stt_debug_capture?: boolean;
  tx_conditioning?: boolean;
  vox_primer_enabled?: boolean;
  vox_primer_ms?: number;
  vox_primer_word_enabled?: boolean;
  vox_primer_word?: string;
  ptt_mode?: string;
  ptt_serial_port?: string;
  ptt_serial_line?: string;
  monitor_passthrough?: boolean;
  attendance_enabled?: boolean;
  saved_phrases?: string[];
  /** Installed plugins: manifest + enabled state + config schema/values. */
  plugins?: PluginManifest[];
  /** Quick-message shortcuts offered on the kiosk display's "I'm OK" screen. */
  display_quick_messages?: string[];
  /** Own station coordinates; null until an admin sets them. The map centres
   *  here, and distance/bearing are only computed when both are present. */
  station_lat?: number | null;
  station_lon?: number | null;
  /** Remote XYZ tile template, used only when no offline pack is installed. */
  map_tiles_url?: string;
  /** True when /data/tiles exists, so the server is serving /tiles itself. */
  map_tiles_local?: boolean;
  /** Positions older than this are dropped rather than plotted stale. */
  position_ttl_minutes?: number;
}

/** One station heard by a position source (mesh node, APRS beacon).
 *
 * Distance, bearing and age are resolved server-side: a wall kiosk's clock is
 * not to be trusted, and the e-ink list has no way to compute great-circle
 * distance itself. All three are null when no own-station position is set.
 */
export interface StationPosition {
  /** Plugin id that heard it — 'meshtastic', 'meshcore', 'aprs_rf'. */
  source: string;
  /** Identifier within that source; unique only per source. */
  node_id: string;
  /** Human-readable name, may be empty. */
  label: string;
  lat: number;
  lon: number;
  alt_m: number | null;
  /** Seconds since the fix was heard. */
  age_s: number;
  distance_km: number | null;
  bearing_deg: number | null;
  /** 16-point compass abbreviation, e.g. 'NNE'. */
  compass: string | null;
  /** Source-specific extras (SNR, APRS comment, symbol...), all strings. */
  extra: Record<string, string>;
}

export interface PositionsMsg {
  type: 'positions';
  stations: StationPosition[];
}

/** One declarative setting a plugin exposes; the frontend renders a form field. */
export interface PluginConfigField {
  key: string;
  label: string;
  type: 'bool' | 'text' | 'number' | 'select' | string;
  default: unknown;
  help: string;
  options: [string, string][];
  minimum: number | null;
  maximum: number | null;
}

/** Declarative "this plugin caps the message input like a mesh bridge" capability.
 *  Keys reference fields in the plugin's own config namespace. */
export interface PluginTxComposition {
  max_len_key: string;
  separator_key: string;
  hint: string;
}

/** An installed plugin's manifest + current state, broadcast in StatusMsg.
 *  Drives the admin Plugins manager (enable/disable, settings form, mutual
 *  exclusion, load errors). State lives under config["plugins"][id]. */
export interface PluginManifest {
  id: string;
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  /** Plugin ids that cannot be co-enabled (enabling this one disables them). */
  conflicts_with: string[];
  config_schema: PluginConfigField[];
  /** Current values for each config_schema field (stored value or its default). */
  config: Record<string, unknown>;
  tx_composition: PluginTxComposition | null;
  /** Present if the plugin failed to load (shown in the UI; not registered). */
  error?: string;
}

export interface ContactsMsg {
  type: 'contacts';
  contacts: Contact[];
}

export interface TxStatusMsg {
  type: 'tx_status';
  status: 'transmitting' | 'idle';
}

export interface TxEchoMsg {
  type: 'tx_echo';
  ts: string;
  callsign: string;
  operator: string;
  display_name: string;
  text: string;
  target_call: string;
  target_name: string;
}

// Chat-only line — shared to all operators' logs but never keyed over the
// radio. Per-recipient profanity-filtered server-side (like rx transcriptions).
export interface ChatEchoMsg {
  type: 'chat_echo';
  ts: string;
  display_name: string;
  operator: string;
  callsign: string;
  text: string;
}

export interface SystemMsgMsg {
  type: 'system_msg';
  text: string;
}

// One entry of the shared stream backfill (rx/tx/chat), as recorded server-side.
export type StoredStreamMsg = RxMessageMsg | TxEchoMsg | ChatEchoMsg;

// Sent once on connect: the whole shared message stream since the last clear.
export interface ChatHistoryMsg {
  type: 'chat_history';
  messages: StoredStreamMsg[];
}

// Broadcast when an admin clears the chat — every client wipes its local log.
export interface ChatClearedMsg {
  type: 'chat_cleared';
}

// Attendance
export interface AttendanceStation {
  callsign: string;
  name: string;
  location: string;
  gmrs: string;
  ham: string;
}

export interface SessionAttendanceMsg {
  type: 'session_attendance';
  stations: AttendanceStation[];
}

// Journals
export interface JournalEntry {
  exported_at: string;
  title: string;
  callsigns: string[];
  callsigns_locations: Array<{ callsign: string; location: string }>;
  transcript: string;
  summary: string;
  _file: string;
  published?: boolean;
}

export interface JournalsMsg {
  type: 'journals';
  journals: JournalEntry[];
}

export interface JournalResultMsg {
  type: 'journal_result';
  title: string;
  summary: string;
  callsigns_locations: Array<{ callsign: string; location: string }>;
}

export interface JournalErrorMsg {
  type: 'journal_error';
  detail: string;
}

export interface JournalSavedMsg {
  type: 'journal_saved';
  path: string;
}

export interface JournalDeletedMsg {
  type: 'journal_deleted';
  file_path: string;
}

export interface JournalPublishedMsg {
  type: 'journal_published';
  title: string;
}

export interface JournalUnpublishedMsg {
  type: 'journal_unpublished';
  file_path: string;
}

export interface NetSessionStation {
  callsign: string;
  name: string;
}

export interface NetSessionSummary {
  id: string;
  net_type: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  checkin_count: number;
  stations: NetSessionStation[];
}

export interface NetSessionRosterRow {
  callsign: string;
  name: string;
  location: string;
  status: string;
  traffic: string | null;
  checkin_time: string;
  verified: boolean;
  /** "radio" for a coordinator-entered station, "" for a self check-in.
   *  Optional because records written before this field existed lack it. */
  via?: string;
  /** True when the round-table called this station and got no reply.
   *  Optional because records written before this field existed lack it. */
  no_answer?: boolean;
}

export interface NetSessionDetail {
  id: string;
  net_type: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  roster: NetSessionRosterRow[];
  transcript: string;
}

export interface AttendanceStatRow {
  callsign: string;
  name: string;
  total_nets: number;
  attended_of_recent: number;
  recent_window: number;
  current_streak: number;
  last_seen: string;
}

export interface NetSessionsMsg {
  type: 'net_sessions';
  sessions: NetSessionSummary[];
  stats: AttendanceStatRow[];
}

export interface NetSessionMsg {
  type: 'net_session';
  session: NetSessionDetail | null;
}

export interface NetSessionDeletedMsg {
  type: 'net_session_deleted';
  id: string;
}

// FCC & callsign features (server → client)
export interface PendingStationsMsg {
  type: 'pending_stations';
  stations: Array<{ callsign: string; name: string; location: string }>;
}

export interface ContactAutoAddedMsg {
  type: 'contact_auto_added';
  callsign: string;
  name: string;
}

export interface FccLookupResultMsg {
  type: 'fcc_lookup_result';
  callsign: string;
  status: string;
  license_name: string;
  license_location: string;
  license_city: string;
  gmrs_callsign: string;
  ham_callsign: string;
}

export interface VerifyAllCompleteMsg {
  type: 'verify_all_complete';
}

export interface VocabularyRescannedMsg {
  type: 'vocabulary_rescanned';
  term_count: number;
  callsign_count: number;
}

// STT calibration wizard — read a canned passage into the radio, sweep gain
// mode / noise profile / Whisper model against it, apply the best combo.
export interface CalibrationTextMsg {
  type: 'calibration_text';
  text: string;
}

export interface CalibrationStartedMsg {
  type: 'calibration_started';
}

export interface CalibrationResultEntry {
  model: string;
  gain_mode: string;
  noise_profile: boolean;
  wer: number;
  hypothesis: string;
}

export interface CalibrationProgressMsg extends CalibrationResultEntry {
  type: 'calibration_progress';
  index: number;
  total: number;
}

export interface CalibrationResultMsg {
  type: 'calibration_result';
  results: CalibrationResultEntry[];
  recommended: CalibrationResultEntry | null;
}

export interface CalibrationErrorMsg {
  type: 'calibration_error';
  detail: string;
}

export interface CalibrationAppliedMsg {
  type: 'calibration_applied';
}

export interface OnlineStatusMsg {
  type: 'online_status';
  online: boolean;
}

// Placeholder token prompt (server → client)
export interface PromptTokenMsg {
  type: 'prompt_token';
  tokens: string[];
  original_text: string;
  target_call: string;
  target_name: string;
  operator: string;
  callsign: string;
}

// Spectrogram
export interface SpectrogramRowMsg {
  type: 'spectrogram_row';
  row: number[];
  vad?: boolean;
  squelch?: boolean;
}

export interface InputDeviceOption {
  label: string;
  id: string | number;
}

export interface MonitorSinkOption {
  label: string;
  sink_id: string;
}

export interface InputDevicesMsg {
  type: 'input_devices';
  devices: InputDeviceOption[];
  monitor_sinks: MonitorSinkOption[];
  current_input_device: string | number;
  current_monitor_sink: string;
}

export interface OutputDeviceOption {
  label: string;
  // Device name, or -1 for the system default. Names are used because
  // PortAudio indices shift when a busy card drops out of the scan.
  id: string | number;
}

export interface OutputDevicesMsg {
  type: 'output_devices';
  devices: OutputDeviceOption[];
  current_output_device: string | number;
}

export interface VoiceOption {
  id: string;
  name: string;
  label: string;
}

export interface VoicesListMsg {
  type: 'voices_list';
  voices: VoiceOption[];
}

// User profile and prefs
export interface UserPrefs {
  dark_mode: boolean;
  filter_profanity: boolean;
  listen_only: boolean;
  read_aloud: boolean;
  notifications_enabled: boolean;
  spectro_colormap: 'viridis' | 'grayscale';
  spectro_time_window_s: number;
  tts_voice?: string;
  tts_length_scale?: number;
  aac_mode?: boolean;
  aac_grid?: AACGrid | null; // null = client renders its built-in default grid
  ui_level?: 'simple' | 'operator';
  font_scale?: number;
  high_contrast?: boolean;
  switch_scan?: boolean;
  switch_scan_interval_s?: number; // 1 | 1.5 | 2 | 3
  visual_alerts?: boolean;
  quick_messages?: string[];
  neighborhood_coordinator?: boolean;
}

export interface UserProfile {
  id: string;
  display_name: string;
  avatar_emoji: string;
  operator_name: string;
  callsign: string;
  location: string;
  is_admin: boolean;
  created_at: string;
  role: 'admin' | 'adult' | 'kid';
  prefs: UserPrefs;
}

export interface UserProfileMsg {
  type: 'user_profile';
  profile: UserProfile;
}

export interface ProfilesMsg {
  type: 'profiles';
  profiles: UserProfile[];
}

export interface VoicePreviewAudioMsg {
  type: 'voice_preview_audio';
  data: string; // base64-encoded int16 PCM
  sample_rate: number;
}

export interface RxAudioMsg {
  type: 'rx_audio';
  data: string; // base64-encoded int16 PCM
  sample_rate: number;
}

// NCS — Net Control Station plugin messages (server → client)
export interface NCSEntry {
  callsign: string;
  status: 'CheckedIn' | 'Standby' | 'CheckedOut' | 'LoggedOut';
  traffic: 'Routine' | 'Priority' | 'Emergency' | 'General' | 'Short Term' | 'IN-n-Out';
  name: string;
  location: string;
  checkin_time: number; // Unix timestamp
  verified?: boolean;
  called?: boolean; // round-table: already called this round
}

export interface NCSAlert {
  id: string;
  event: string;
  headline: string;
  zone: string;
  severity: string;
}

export interface NCSStateMsg {
  type: 'ncs_state';
  active: boolean;
  roster: NCSEntry[];
  zone: string;
  current_call?: string; // round-table: callsign currently being called
}

export interface NCSRosterUpdateMsg {
  type: 'ncs_roster_update';
  roster: NCSEntry[];
  current_call?: string;
}

export interface NCSAlertMsg extends NCSAlert {
  type: 'ncs_alert';
}

export interface NCSReplayAudioMsg {
  type: 'ncs_replay_audio';
  data: string; // base64-encoded int16 PCM (empty string = no buffer)
  sample_rate: number;
}

export interface NCSBreakBreakAckMsg {
  type: 'ncs_break_break_ack';
}

export interface NCSJournalSavedMsg {
  type: 'ncs_journal_saved';
  path: string;
}

// SKYWARN spot report
export type SpotHazard =
  | 'tornado'
  | 'funnel_cloud'
  | 'wall_cloud'
  | 'hail'
  | 'wind'
  | 'flooding'
  | 'snow'
  | 'other';

export interface NCSSpotReportPayload {
  type: 'ncs_spot_report';
  hazard: SpotHazard;
  hail_size_in?: number;
  wind_mph?: number;
  wind_method?: 'estimated' | 'measured';
  wind_damage?: string;
  rain_amount_in?: number;
  rain_duration_min?: number;
  snow_amount_in?: number;
  detail?: string;
  location: string;
  observed_at?: string; // ISO; server defaults to now
}

export interface NCSSpotReportSentMsg {
  type: 'ncs_spot_report_sent';
  text: string;
  ts: string;
}

export interface NCSSpotReportErrorMsg {
  type: 'ncs_spot_report_error';
  detail: string;
}

// Net scripts (preamble / closing)
export interface NCSScriptSentMsg {
  type: 'ncs_script_sent';
  which: 'preamble' | 'closing';
  text: string;
}

export interface NCSScriptErrorMsg {
  type: 'ncs_script_error';
  detail: string;
}

// Round-table caller
export interface NCSRoundCompleteMsg {
  type: 'ncs_round_complete';
}

// Family activity — presence roster + check-in reminders (server → client)
export interface FamilyPresenceEntry {
  user_id: string;
  display_name: string;
  avatar_emoji: string;
  last_heard: string | null;
  last_ok: string | null;
  missed_checkin: boolean;
}

export interface FamilyPresenceMsg {
  type: 'family_presence';
  entries: FamilyPresenceEntry[];
}

export interface FamilyRemindersMsg {
  type: 'family_reminders';
  reminders: Record<string, { time: string; enabled: boolean }>;
}

// Neighborhood activity — net roster/round-table, incident reports, and
// street alerts (server → client). See backend/neighborhood/net.py and
// backend/persistence/incidents.py for the shapes this mirrors.
export interface NeighborhoodRosterRow {
  user_id: string;
  callsign: string;
  name: string;
  location: string;
  status: 'checked_in' | 'standby' | 'checked_out';
  checkin_time: string;
  called: boolean;
  /** Present only on stations a coordinator checked in off the air. */
  via?: 'radio';
  /** True when the round-table called this station and got no reply.
   *  Optional so older server payloads (or NCS-shaped rows) still typecheck. */
  no_answer?: boolean;
}

export interface NeighborhoodStateMsg {
  type: 'neighborhood_state';
  active: boolean;
  roster: NeighborhoodRosterRow[];
  current_call: string | null;
  net_day: string;
  net_time: string;
}

export interface IncidentEntry {
  id: string;
  category: string;
  description: string;
  location: string;
  reporter: string;
  ts: string;
}

export interface NeighborhoodIncidentsMsg {
  type: 'neighborhood_incidents';
  incidents: IncidentEntry[];
}

export interface NeighborhoodAlertMsg {
  type: 'neighborhood_alert';
  id: string;
  message: string;
  issued_by: string;
  ts: string;
}

export interface NeighborhoodIncidentSentMsg {
  type: 'neighborhood_incident_sent';
  text: string;
  ts: string;
}

export interface NeighborhoodIncidentErrorMsg {
  type: 'neighborhood_incident_error';
  detail: string;
}

export interface NeighborhoodJournalSavedMsg {
  type: 'neighborhood_journal_saved';
  path: string;
}

// Kiosk display device tokens — long-lived, revocable credentials that let a
// dedicated display device authenticate over WS without a user login
// (server → client; admin-managed via AdminPanel).
export interface DeviceTokenRecord {
  id: string;
  label: string;
  created_at: string;
  last_seen: string | null;
  /** E-ink display mode for this wall panel. Absent on legacy records → false. */
  eink?: boolean;
  /** Hand-sorted tile order for this panel. Absent on legacy records → []. */
  order?: string[];
  /** Present only in the one-time device_token_created reply. */
  token?: string;
}

export interface DeviceTokensMsg {
  type: 'device_tokens';
  tokens: DeviceTokenRecord[];
}

export interface DeviceTokenCreatedMsg {
  type: 'device_token_created';
  record: DeviceTokenRecord;
  /** Six-digit, single-use, ten-minute code the admin reads to the display. */
  pairing_code?: string;
}

// A fresh pairing code for an existing display (re-pair without revoking).
export interface DeviceTokenPairCodeMsg {
  type: 'device_token_pair_code';
  id: string;
  pairing_code: string;
}

// Kiosk display — per-device config sent once on connect (server → client).
export interface DisplayConfigMsg {
  type: 'display_config';
  eink: boolean;
  /** Absent on servers older than this feature → treat as no stored order. */
  order?: string[];
}

// Kiosk display — server ack for a display's own actions (server → client).
export interface DisplayAckMsg {
  type: 'display_ack';
  action: 'im_ok' | 'quick_message' | 'order';
}

export type WsMessage =
  | RxMessageMsg
  | RxMessagePatchMsg
  | StatusMsg
  | ContactsMsg
  | TxStatusMsg
  | TxEchoMsg
  | ChatEchoMsg
  | ChatHistoryMsg
  | ChatClearedMsg
  | SystemMsgMsg
  | SessionAttendanceMsg
  | JournalsMsg
  | JournalResultMsg
  | JournalErrorMsg
  | JournalSavedMsg
  | JournalDeletedMsg
  | PromptTokenMsg
  | PendingStationsMsg
  | ContactAutoAddedMsg
  | FccLookupResultMsg
  | VerifyAllCompleteMsg
  | VocabularyRescannedMsg
  | CalibrationTextMsg
  | CalibrationStartedMsg
  | CalibrationProgressMsg
  | CalibrationResultMsg
  | CalibrationErrorMsg
  | CalibrationAppliedMsg
  | OnlineStatusMsg
  | SpectrogramRowMsg
  | InputDevicesMsg
  | OutputDevicesMsg
  | UserProfileMsg
  | ProfilesMsg
  | JournalPublishedMsg
  | JournalUnpublishedMsg
  | VoicesListMsg
  | VoicePreviewAudioMsg
  | RxAudioMsg
  | NCSStateMsg
  | NCSRosterUpdateMsg
  | NCSAlertMsg
  | NCSReplayAudioMsg
  | NCSBreakBreakAckMsg
  | NCSJournalSavedMsg
  | NCSSpotReportSentMsg
  | NCSSpotReportErrorMsg
  | NCSScriptSentMsg
  | NCSScriptErrorMsg
  | NCSRoundCompleteMsg
  | FamilyPresenceMsg
  | FamilyRemindersMsg
  | NeighborhoodStateMsg
  | NeighborhoodIncidentsMsg
  | NeighborhoodAlertMsg
  | NeighborhoodIncidentSentMsg
  | NeighborhoodIncidentErrorMsg
  | NeighborhoodJournalSavedMsg
  | DeviceTokensMsg
  | DeviceTokenCreatedMsg
  | DeviceTokenPairCodeMsg
  | DisplayConfigMsg
  | DisplayAckMsg
  | VoiceTxAckMsg
  | VoiceTxErrorMsg
  | { type: 'voice_preview_done' }
  | { type: 'error'; detail?: string }
  | NetSessionsMsg
  | NetSessionMsg
  | NetSessionDeletedMsg
  | PositionsMsg
  | VoiceTxAckMsg
  | VoiceTxErrorMsg;

export interface TxMessagePayload {
  type: 'tx_message';
  text: string;
  operator: string;
  callsign: string;
  target_call?: string;
  target_name?: string;
  // Voice/speed the backend should transmit in: the named operator's profile
  // (the [tx] [name] convention). Resolved server-side via get_by_display_name;
  // falls back to the station default when unknown.
  voice_as?: string;
  // Raw AAC button texts this message was composed from. For kid accounts the
  // server validates these against the stored aac_grid and rebuilds the text
  // itself; for adults they're inert.
  aac_chunks?: string[];
}

// Chat-only line — Client → Server (sent via send(), NOT part of WsMessage union).
export interface ChatMessagePayload {
  type: 'chat_message';
  text: string;
  operator: string;
  callsign: string;
}

// Voice PTT — Client → Server payloads (sent via send(), NOT part of WsMessage union)
export interface VoiceTxStartPayload {
  type: 'voice_tx_start';
  callsign: string;
  operator: string;
}

export interface VoiceTxChunkPayload {
  type: 'voice_tx_chunk';
  data: string; // base64 int16 PCM, 16 kHz mono
}

export interface VoiceTxEndPayload {
  type: 'voice_tx_end';
}

export interface VoiceTxCancelPayload {
  type: 'voice_tx_cancel';
}

export interface TxAbortPayload {
  type: 'tx_abort';
}

// Family activity — Client → Server payloads (sent via send(), NOT part of WsMessage union)
export interface FamilyStatusPayload {
  type: 'family_status';
  status: 'ok';
}

export interface SetFamilyReminderPayload {
  type: 'set_family_reminder';
  user_id: string;
  time: string | null;
  enabled: boolean;
}

export interface SetRolePayload {
  type: 'set_role';
  user_id: string;
  role: 'admin' | 'adult' | 'kid';
}

export interface SetUserQuickMessagesPayload {
  type: 'set_user_quick_messages';
  user_id: string;
  quick_messages: string[];
}

// Neighborhood activity — Client → Server payloads (sent via send(), NOT
// part of WsMessage union). Identity for check-in/incident/alert text comes
// from the connection's own profile server-side — never client-supplied.
export interface NeighborhoodCheckinPayload {
  type: 'neighborhood_checkin';
}

export interface NeighborhoodStatusPayload {
  type: 'neighborhood_status';
  status: 'checked_in' | 'standby' | 'checked_out';
  user_id?: string;
}

export interface NeighborhoodStartPayload {
  type: 'neighborhood_start';
}

export interface NeighborhoodEndPayload {
  type: 'neighborhood_end';
}

export interface NeighborhoodCallNextPayload {
  type: 'neighborhood_call_next';
}

export interface NeighborhoodCallResetPayload {
  type: 'neighborhood_call_reset';
}

/** Coordinator-only: flag/unflag a station the round couldn't raise. */
export interface NeighborhoodNoAnswerPayload {
  type: 'neighborhood_no_answer';
  user_id: string;
  no_answer: boolean;
}

/** Coordinator-only: call this station out of order (round-table). */
export interface NeighborhoodCallStationPayload {
  type: 'neighborhood_call_station';
  user_id: string;
}

/** Admin-only (stricter than the coordinator gate on the other net
 *  controls): empties the roster, leaving an in-progress net running. */
export interface NeighborhoodClearCheckinsPayload {
  type: 'neighborhood_clear_checkins';
}

/** Admin-only: the server journals the log before wiping it, and refuses to
 *  wipe if that journal save fails. */
export interface NeighborhoodClearIncidentsPayload {
  type: 'neighborhood_clear_incidents';
}

/** Coordinator-only: check in a neighbor who called in over the air and has
 *  no account here. Unlike neighborhood_checkin, the identity is supplied by
 *  the client — the server gates on the coordinator grant instead. */
export interface NeighborhoodCheckinRadioPayload {
  type: 'neighborhood_checkin_radio';
  callsign: string;
  name: string;
  location: string;
  save_contact?: boolean;
}

/** Coordinator-only: drop a radio check-in row. The server refuses any
 *  user_id that isn't a radio station key. */
export interface NeighborhoodRemoveStationPayload {
  type: 'neighborhood_remove_station';
  user_id: string;
}

export interface NeighborhoodIncidentReportPayload {
  type: 'neighborhood_incident_report';
  category: string;
  description: string;
  location: string;
}

export interface NeighborhoodStreetAlertPayload {
  type: 'neighborhood_street_alert';
  message: string;
}

export interface SetNeighborhoodCoordinatorPayload {
  type: 'set_neighborhood_coordinator';
  user_id: string;
  coordinator: boolean;
}

// Kiosk display — Client → Server payloads (sent via send(), NOT part of
// WsMessage union). Identity comes from the device token's session server-side.
export interface DisplayImOkPayload {
  type: 'display_im_ok';
  user_id: string;
}

export interface DisplayQuickMessagePayload {
  type: 'display_quick_message';
  text: string;
}

// Voice PTT — Server → Client messages (part of WsMessage union)
export interface VoiceTxAckMsg {
  type: 'voice_tx_ack';
}

export interface VoiceTxErrorMsg {
  type: 'voice_tx_error';
  detail: string;
}
