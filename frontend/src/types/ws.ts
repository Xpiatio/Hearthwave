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
  speaker_callsign: string | null;
  speaker_name: string | null;
  cluster_label: string | null;
  // [start, end, canonical_callsign] tuples computed by the backend.
  // Spans reference original character positions in `text`, handling NATO-phonetic,
  // spaced, hyphenated, and compact callsign forms.
  callsign_spans?: Array<[number, number, string]>;
}

export interface RxMessagePatchMsg {
  type: 'rx_message_patch';
  utterance_id: string;
  callsign_spans: Array<[number, number, string]>;
}

export interface SpeakerEnrolledMsg {
  type: 'speaker_enrolled';
  callsign: string;
  name: string;
  sample_count: number;
}

export interface SpeakerResetMsg {
  type: 'speaker_reset';
  callsign: string;
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
  spectro_colormap?: 'viridis' | 'grayscale';
  spectro_freq_range?: 'voice' | 'full';
  spectro_time_window_s?: number;
  input_device?: string | number;
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

export interface SystemMsgMsg {
  type: 'system_msg';
  text: string;
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
  panel_order: string[];
  filter_profanity: boolean;
  listen_only: boolean;
  read_aloud: boolean;
  notifications_enabled: boolean;
  spectro_colormap: 'viridis' | 'grayscale';
  spectro_time_window_s: number;
  tts_voice?: string;
  tts_length_scale?: number;
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

export interface TxAudioMsg {
  type: 'tx_audio';
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
  status: 'CheckedIn' | 'Standby' | 'LoggedOut';
  traffic: 'Routine' | 'Priority' | 'Emergency';
  name: string;
  location: string;
  checkin_time: number; // Unix timestamp
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
}

export interface NCSRosterUpdateMsg {
  type: 'ncs_roster_update';
  roster: NCSEntry[];
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

export type WsMessage =
  | RxMessageMsg
  | RxMessagePatchMsg
  | StatusMsg
  | ContactsMsg
  | TxStatusMsg
  | TxEchoMsg
  | SystemMsgMsg
  | SpeakerEnrolledMsg
  | SpeakerResetMsg
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
  | OnlineStatusMsg
  | SpectrogramRowMsg
  | InputDevicesMsg
  | UserProfileMsg
  | ProfilesMsg
  | JournalPublishedMsg
  | VoicesListMsg
  | VoicePreviewAudioMsg
  | TxAudioMsg
  | RxAudioMsg
  | NCSStateMsg
  | NCSRosterUpdateMsg
  | NCSAlertMsg
  | NCSReplayAudioMsg
  | NCSBreakBreakAckMsg
  | NCSJournalSavedMsg
  | VoiceTxAckMsg
  | VoiceTxErrorMsg
  | { type: 'voice_preview_done' }
  | { type: 'error'; detail?: string };

export interface TxMessagePayload {
  type: 'tx_message';
  text: string;
  operator: string;
  callsign: string;
  target_call?: string;
  target_name?: string;
}

// Voice PTT (Client → Server payloads, sent via send(), not part of WsMessage union)
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

// Voice PTT (Server → Client messages, part of WsMessage union)
export interface VoiceTxAckMsg {
  type: 'voice_tx_ack';
}

export interface VoiceTxErrorMsg {
  type: 'voice_tx_error';
  detail: string;
}
