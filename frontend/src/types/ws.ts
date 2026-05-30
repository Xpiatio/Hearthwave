export interface Contact {
  name: string;
  callsign: string;
  location?: string;
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

// Spectrogram
export interface SpectrogramRowMsg {
  type: 'spectrogram_row';
  row: number[];
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
  | SpectrogramRowMsg;

export interface TxMessagePayload {
  type: 'tx_message';
  text: string;
  operator: string;
  callsign: string;
  target_call?: string;
  target_name?: string;
}
