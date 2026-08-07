export interface AdminConfig {
  stationCallsign: string;
  stationName: string;
  stationLocation: string;
  stationVoice: string;
  stationLengthScale: number;
  geminiApiKeySet: boolean;
  journalsDir: string;
  ncsZone: string;
  ncsPreambleText: string;
  ncsClosingText: string;
  rxMode: string;
  netDay: string;
  netTime: string;
  /** Own station coordinates; null until an admin sets them. Distance and
   *  bearing on the positions panel need both. */
  stationLat: number | null;
  stationLon: number | null;
  /** True when the server found an offline tile pack and is serving /tiles. */
  mapTilesLocal: boolean;
  /** Remote XYZ tile template; used only when there is no offline pack. */
  mapTilesUrl: string;
  positionTtlMinutes: number;
  /** Quick-message shortcuts offered on the kiosk display's "I'm OK" screen. */
  display_quick_messages: string[];
}

export interface JournalResultDraft {
  title: string;
  summary: string;
  callsigns_locations: Array<{ callsign: string; location: string }>;
}

export interface PendingStation {
  callsign: string;
  name: string;
  location: string;
}

export interface PromptState {
  tokens: string[];
  originalText: string;
  operator: string;
  callsign: string;
  targetCall: string;
  targetName: string;
}
