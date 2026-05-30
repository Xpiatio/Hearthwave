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
  state: 'transmitting' | 'idle';
}

export interface SystemMsgMsg {
  type: 'system_msg';
  text: string;
}

export type WsMessage =
  | RxMessageMsg
  | StatusMsg
  | ContactsMsg
  | TxStatusMsg
  | SystemMsgMsg
  | SpeakerEnrolledMsg
  | SpeakerResetMsg;

export interface TxMessagePayload {
  type: 'tx_message';
  text: string;
  operator: string;
  callsign: string;
  target_call?: string;
  target_name?: string;
}
