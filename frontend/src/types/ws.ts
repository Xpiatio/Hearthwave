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
  spectro_colormap?: string;
  spectro_freq_range?: string;
  spectro_time_window_s?: number;
  // Admin-editable identity fields
  station_callsign?: string;
  station_name?: string;
  station_location?: string;
  gemini_api_key_set?: boolean;
  journals_dir?: string;
}

export interface ContactsMsg {
  type: 'contacts';
  contacts: Contact[];
}

export interface TxStatusMsg {
  type: 'tx_status';
  status: 'transmitting' | 'idle';
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

export type WsMessage =
  | RxMessageMsg
  | StatusMsg
  | ContactsMsg
  | TxStatusMsg
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
  | SpectrogramRowMsg;

export interface TxMessagePayload {
  type: 'tx_message';
  text: string;
  operator: string;
  callsign: string;
  target_call?: string;
  target_name?: string;
}
