export interface AdminConfig {
  stationCallsign: string;
  stationName: string;
  stationLocation: string;
  stationVoice: string;
  stationLengthScale: number;
  geminiApiKeySet: boolean;
  journalsDir: string;
  ncsZone: string;
  rxMode: string;
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
