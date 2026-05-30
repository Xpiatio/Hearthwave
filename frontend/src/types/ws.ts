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
  | SystemMsgMsg;

export interface TxMessagePayload {
  type: 'tx_message';
  text: string;
  operator: string;
  callsign: string;
}
