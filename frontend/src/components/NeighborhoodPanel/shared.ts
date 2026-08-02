import type { Contact, IncidentEntry, NeighborhoodAlertMsg, NeighborhoodRosterRow } from '../../types/ws';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';
import type { TxComposition } from '../../plugins';

/** Props shared by NeighborhoodPanel (the switch + its stacked view) and
 *  CoordinatorDashboard (the wide-screen ops view NeighborhoodPanel
 *  switches to). Lives in its own module, rather than in either component
 *  file, so the two can import it without importing each other —
 *  NeighborhoodPanel renders CoordinatorDashboard, so the reverse import
 *  that used to live here would be a cycle. */
export interface NeighborhoodPanelProps {
  roster: NeighborhoodRosterRow[];
  netActive: boolean;
  currentCall: string | null;
  incidents: IncidentEntry[];
  alerts: NeighborhoodAlertMsg[];
  netDay: string;
  netTime: string;
  isCoordinator: boolean;
  /** Admin-only controls (the two board clears). Stricter than isCoordinator
   *  on purpose: running a net is a coordinator job, wiping the board is an
   *  admin one. Server re-checks — this only hides the buttons. */
  isAdmin: boolean;
  isKid: boolean;
  myUserId: string;
  onCheckin: () => void;
  onClearCheckins: () => void;
  onClearIncidents: () => void;
  onStatusChange: (status: 'checked_in' | 'standby' | 'checked_out') => void;
  onIncidentReport: (p: { category: string; description: string; location: string }) => void;
  incidentError: string | null;
  onStreetAlert: (message: string) => void;
  onStartNet: () => void;
  onEndNet: () => void;
  onCallNext: () => void;
  onNewRound: () => void;
  onGoHome: () => void;
  /** Contact book, used to prefill the radio check-in form. */
  contacts: Contact[];
  onRadioCheckin: (p: { callsign: string; name: string; location: string; saveContact: boolean }) => void;
  onStationStatusChange: (userId: string, status: 'checked_in' | 'standby' | 'checked_out') => void;
  onRemoveStation: (userId: string) => void;
  /** Coordinator-only: call this station out of order (round-table). */
  onCallStation: (userId: string) => void;
  /** Coordinator-only: flag/unflag a station the round couldn't raise. */
  onNoAnswer: (userId: string, noAnswer: boolean) => void;

  /** True when this operator's session is receive-only (no transmit
   *  capability) — honored the same way DesktopApp gates its own
   *  MessageInput (`!listenOnly && !isKid`). Optional so the many existing
   *  mounts and tests that predate this flag keep compiling unchanged;
   *  treated as `false` when absent. Only CoordinatorDashboard's message
   *  composer reads it — the stacked view never renders a transmit box. */
  listenOnly?: boolean;

  /** Dashboard-only (present when App mounts the panel for a desktop
   *  session): live RX/chat entries and TX plumbing for the coordinator
   *  ops view. Optional here so the stacked view and every existing test's
   *  makeProps keep compiling unchanged — NeighborhoodPanel only switches
   *  to CoordinatorDashboard once `messages` is actually provided. */
  messages?: ChatEntry[];
  transmitting?: boolean;
  showCallsignChips?: boolean;
  onSendMessage?: (text: string, targetCall: string, targetName: string) => void;
  onChat?: (text: string) => void;
  onStandaloneId?: () => void;
  txComposition?: TxComposition | null;
}

/** Resolve a raw current_call user_id (what the backend actually sends —
 *  see backend/neighborhood/net.py's call_next) to something a human can
 *  read: display name, falling back to callsign, falling back to nothing
 *  (never the raw user_id — "Current turn: dana-3f2a" is the bug this
 *  fixes) if the roster row can't be found or is missing both fields. */
export function currentCallLabel(userId: string, roster: NeighborhoodRosterRow[]): string {
  const row = roster.find((r) => r.user_id === userId);
  return row?.name || row?.callsign || '';
}

export function formatAlertTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}
