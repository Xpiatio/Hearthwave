import { useState, useRef } from 'react';
import {
  Box,
  BottomNavigation,
  BottomNavigationAction,
  Snackbar,
  Alert,
} from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import PeopleIcon from '@mui/icons-material/People';
import ArticleIcon from '@mui/icons-material/Article';
import FamilyRestroomIcon from '@mui/icons-material/FamilyRestroom';
import HolidayVillageIcon from '@mui/icons-material/HolidayVillage';
import { MobileTopBar } from './MobileTopBar';
import { ChatDisplay } from '../ChatDisplay/ChatDisplay';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';
import { MessageInput } from '../MessageInput/MessageInput';
import type { MessageInputHandle } from '../MessageInput/MessageInput';
import { QuickMessages } from '../QuickMessages/QuickMessages';
import { AttendancePanel } from '../AttendancePanel/AttendancePanel';
import { JournalPanel } from '../JournalPanel/JournalPanel';
import { FamilyPanel } from '../FamilyPanel/FamilyPanel';
import { PresetComposer } from '../FamilyPanel/PresetComposer';
import { NeighborhoodPanel } from '../NeighborhoodPanel/NeighborhoodPanel';
import { PendingStationsBar } from '../PendingStationsBar/PendingStationsBar';
import { ContactsDialog } from '../ContactsDialog/ContactsDialog';
import type { TxComposition } from '../../plugins';
import type {
  StatusMsg,
  Contact,
  AttendanceStation,
  JournalEntry,
  FamilyPresenceEntry,
  FccLookupResultMsg,
  UserProfile,
  VoiceOption,
  WsMessage,
  NeighborhoodStateMsg,
  IncidentEntry,
  NeighborhoodAlertMsg,
} from '../../types/ws';
import type { AdminConfig, JournalResultDraft, PendingStation } from '../../types/appTypes';

export interface MobileAppProps {
  // Identity & connection
  profile: UserProfile;
  effectiveCallsign: string;
  connected: boolean;
  isOnline: boolean | null;
  showCallsignChips: boolean;
  /** Interface tier — gates operator-only tabs/panels (Stations, Journal). */
  uiLevel: 'simple' | 'operator';
  /** Kid accounts: no Settings entry point, free-text composer is replaced
   *  by a PresetComposer, and the Family panel hides reminder editors. */
  isKid: boolean;
  quickMessages: string[];

  // Family activity — names match App.tsx's sharedProps so the spread at
  // the call site (`<MobileApp {...sharedProps} .../>`) wires them up.
  familyPresence: FamilyPresenceEntry[];
  familyReminders: Record<string, { time: string; enabled: boolean }>;
  sendImOk: () => void;
  sendSetReminder: (userId: string, time: string | null, enabled: boolean) => void;

  // Neighborhood activity — same sharedProps-spread convention as Family above.
  isCoordinator: boolean;
  neighborhoodState: NeighborhoodStateMsg | null;
  incidents: IncidentEntry[];
  neighborhoodAlerts: NeighborhoodAlertMsg[];
  incidentError: string | null;
  sendNeighborhoodCheckin: () => void;
  sendNeighborhoodStatus: (status: 'checked_in' | 'standby', userId?: string) => void;
  sendIncidentReport: (category: string, description: string, location: string) => void;
  sendStreetAlert: (message: string) => void;
  sendNeighborhoodStart: () => void;
  sendNeighborhoodEnd: () => void;
  sendNeighborhoodCallNext: () => void;
  sendNeighborhoodCallReset: () => void;

  // Core data
  messages: ChatEntry[];
  contacts: Contact[];
  radioStatus: StatusMsg | null;
  transmitting: boolean;
  lastMessage: WsMessage | null;
  channelClear: boolean;

  // Attendance
  attendanceStations: AttendanceStation[];
  onClearAttendance: () => void;

  // Journal
  journals: JournalEntry[];
  journalResult: JournalResultDraft | null;
  journalGenerating: boolean;
  journalError: string | null;
  rxTexts: string[];
  rxCallsigns: string[];
  onListJournals: () => void;
  onGenerate: (transcript: string, callsigns: string[]) => void;
  onSaveJournal: (
    title: string,
    summary: string,
    callsigns_locations: Array<{ callsign: string; location: string }>,
    transcript: string,
  ) => void;
  onDeleteJournal: (file_path: string) => void;
  onPublishJournal: (file_path: string) => void;
  onUnpublishJournal: (file_path: string) => void;
  onDismissJournalResult: () => void;

  // TX / PTT
  listenOnly: boolean;
  onSend: (text: string, targetCall: string, targetName: string) => void;
  onChat: (text: string) => void;
  onStandaloneId: () => void;
  txComposition: TxComposition | null;
  onVoicePttStart: () => void;
  onVoicePttChunk: (b64: string) => void;
  onVoicePttEnd: () => void;
  onVoicePttCancel: () => void;
  onTxAbort: () => void;

  // User prefs
  sttListening: boolean;
  serviceMode: string;
  readAloud: boolean;
  notificationsEnabled: boolean;
  darkMode: boolean;
  voices: VoiceOption[];
  voicePreviewBusy: boolean;
  onToggleSttListening: () => void;
  onToggleServiceMode: () => void;
  onToggleReadAloud: () => void;
  onToggleNotifications: () => void;
  onToggleListenOnly: () => void;
  onToggleDark: () => void;
  onUpdateProfile: (updates: {
    operator_name?: string;
    callsign?: string;
    location?: string;
    avatar_emoji?: string;
  }) => void;
  onChangePassword: (newPassword: string) => void;
  onLogout: () => void;
  onPreviewVoice: (voiceId: string) => void;
  onSaveTtsPrefs: (prefs: { voice: string; length_scale: number }) => void;

  // Admin / server
  adminConfig: AdminConfig;
  showSettings: boolean;
  onToggleSettings: () => void;

  // Contacts
  showContacts: boolean;
  pendingPrefilledCallsign: string | undefined;
  pendingPrefilledName: string | undefined;
  pendingPrefilledLocation: string | undefined;
  fccLookupResult: FccLookupResultMsg | null;
  verifyAllComplete: boolean;
  onContactsClose: () => void;
  onVerifyAllDismiss: () => void;
  send: (payload: unknown) => void;

  // Pending stations
  pendingStations: PendingStation[];
  onAddPending: (station: PendingStation) => void;
  onDismissPending: (callsign: string) => void;
  onDismissAllPending: () => void;
  // Snackbars
  publishSnack: string | null;
  errorSnack: string | null;
  journalSavedSnack: string | null;
  vocabSnack: string | null;
  onClosePublishSnack: () => void;
  onCloseErrorSnack: () => void;
  onCloseJournalSavedSnack: () => void;
  onCloseVocabSnack: () => void;
}

export function MobileApp({
  profile,
  effectiveCallsign,
  connected,
  showCallsignChips,
  uiLevel,
  isKid,
  quickMessages,
  familyPresence,
  familyReminders,
  sendImOk,
  sendSetReminder,
  isCoordinator,
  neighborhoodState,
  incidents: neighborhoodIncidents,
  neighborhoodAlerts,
  incidentError,
  sendNeighborhoodCheckin,
  sendNeighborhoodStatus,
  sendIncidentReport,
  sendStreetAlert,
  sendNeighborhoodStart,
  sendNeighborhoodEnd,
  sendNeighborhoodCallNext,
  sendNeighborhoodCallReset,
  messages,
  contacts,
  transmitting,
  attendanceStations,
  onClearAttendance,
  journals,
  journalResult,
  journalGenerating,
  journalError,
  rxTexts,
  rxCallsigns,
  onListJournals,
  onGenerate,
  onSaveJournal,
  onDeleteJournal,
  onPublishJournal,
  onUnpublishJournal,
  onDismissJournalResult,
  listenOnly,
  onSend,
  onChat,
  onStandaloneId,
  txComposition,
  onVoicePttStart,
  onVoicePttChunk,
  onVoicePttEnd,
  onVoicePttCancel,
  onTxAbort,
  sttListening,
  readAloud,
  notificationsEnabled,
  darkMode,
  voices,
  voicePreviewBusy,
  onToggleSttListening,
  onToggleReadAloud,
  onToggleNotifications,
  onToggleListenOnly,
  onToggleDark,
  onUpdateProfile,
  onChangePassword,
  onLogout,
  onPreviewVoice,
  onSaveTtsPrefs,
  adminConfig,
  showSettings,
  onToggleSettings,
  showContacts,
  pendingPrefilledCallsign,
  pendingPrefilledName,
  pendingPrefilledLocation,
  fccLookupResult,
  verifyAllComplete,
  onContactsClose,
  onVerifyAllDismiss,
  send,
  pendingStations,
  onAddPending,
  onDismissPending,
  onDismissAllPending,
  publishSnack,
  errorSnack,
  journalSavedSnack,
  vocabSnack,
  onClosePublishSnack,
  onCloseErrorSnack,
  onCloseJournalSavedSnack,
  onCloseVocabSnack,
}: MobileAppProps) {
  const [tab, setTab] = useState<'chat' | 'stations' | 'journal' | 'family' | 'neighborhood'>('chat');
  const messageInputRef = useRef<MessageInputHandle>(null);

  // Stations (attendance) and Journal are operator-only surfaces — they
  // must not render in simple tier, mirroring the isOperatorTier pattern in
  // DesktopApp.tsx (commit 0b6f296). Mobile has no waterfall/spectrogram,
  // RX level meter, or NCS panel, so there's nothing else to gate here.
  // Family and Neighborhood are available in both tiers.
  const isOperatorTier = uiLevel === 'operator';

  // If the tier flips to simple while parked on an operator-only tab, fall
  // back to Chat rather than stranding the user on a hidden panel. `tab`
  // itself is left untouched so the previous selection is restored if the
  // tier flips back to operator. Family/Neighborhood survive the clamp in
  // either tier.
  const activeTab = isOperatorTier ? tab : (tab === 'family' || tab === 'neighborhood') ? tab : 'chat';

  return (
    <Box
      className="app-shell"
      sx={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
    >
      <MobileTopBar
        profile={profile}
        effectiveCallsign={effectiveCallsign}
        connected={connected}
        transmitting={transmitting}
        listenOnly={listenOnly}
        sttListening={sttListening}
        readAloud={readAloud}
        notificationsEnabled={notificationsEnabled}
        darkMode={darkMode}
        voices={voices}
        voicePreviewBusy={voicePreviewBusy}
        stationLengthScale={adminConfig.stationLengthScale}
        showSettings={showSettings}
        isKid={isKid}
        onToggleSttListening={onToggleSttListening}
        onToggleReadAloud={onToggleReadAloud}
        onToggleNotifications={onToggleNotifications}
        onToggleListenOnly={onToggleListenOnly}
        onToggleDark={onToggleDark}
        onVoicePttStart={onVoicePttStart}
        onVoicePttChunk={onVoicePttChunk}
        onVoicePttEnd={onVoicePttEnd}
        onVoicePttCancel={onVoicePttCancel}
        onTxAbort={onTxAbort}
        onUpdateProfile={onUpdateProfile}
        onChangePassword={onChangePassword}
        onLogout={onLogout}
        onPreviewVoice={onPreviewVoice}
        onSaveTtsPrefs={onSaveTtsPrefs}
        onToggleSettings={onToggleSettings}
      />

      <PendingStationsBar
        stations={pendingStations}
        onAdd={onAddPending}
        onDismiss={onDismissPending}
        onDismissAll={onDismissAllPending}
      />

      {/* Chat tab */}
      {activeTab === 'chat' && (
        <Box sx={{ flex: '1 1 auto', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <ChatDisplay
            entries={messages}
            contacts={contacts}
            showCallsignChips={showCallsignChips}
          />
          {!listenOnly && isKid && (
            <PresetComposer quickMessages={quickMessages} onSend={onSend} />
          )}
          {!listenOnly && !isKid && (
            <QuickMessages
              operatorName={profile.operator_name}
              onSelect={(text) => messageInputRef.current?.setText(text)}
            />
          )}
          {!listenOnly && !isKid && (
            <MessageInput
              ref={messageInputRef}
              transmitting={transmitting}
              contacts={contacts}
              onSend={onSend}
              onChat={onChat}
              onStandaloneId={onStandaloneId}
              maxLength={txComposition?.maxLength}
              composeHint={txComposition?.hint}
            />
          )}
        </Box>
      )}

      {/* Family tab — must be a truly conditional mount (not just hidden):
          FamilyPanel's useEscapeToHome hook attaches a document-level
          keydown listener, which would leak/steal Escape if kept alive
          off-screen while another tab is active. */}
      {activeTab === 'family' && (
        <Box sx={{ flex: '1 1 auto', overflowY: 'auto' }}>
          <FamilyPanel
            entries={familyPresence}
            reminders={familyReminders}
            isKid={isKid}
            isAdmin={!!profile.is_admin}
            quickMessages={quickMessages}
            onImOk={sendImOk}
            onQuickMessage={(text) => onSend(text, '', '')}
            onSetReminder={sendSetReminder}
            onGoHome={() => setTab('chat')}
          />
        </Box>
      )}

      {/* Neighborhood tab — conditional mount for the same reason as Family
          above: NeighborhoodPanel also owns a document-level Escape-to-home
          binding via useEscapeToHome. */}
      {activeTab === 'neighborhood' && (
        <Box sx={{ flex: '1 1 auto', overflowY: 'auto' }}>
          <NeighborhoodPanel
            roster={neighborhoodState?.roster ?? []}
            netActive={neighborhoodState?.active ?? false}
            currentCall={neighborhoodState?.current_call ?? null}
            incidents={neighborhoodIncidents}
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
            onGoHome={() => setTab('chat')}
          />
        </Box>
      )}

      {/* Stations tab (operator-only) */}
      {activeTab === 'stations' && (
        <Box sx={{ flex: '1 1 auto', overflowY: 'auto' }}>
          <AttendancePanel
            stations={attendanceStations}
            onClear={onClearAttendance}
          />
        </Box>
      )}

      {/* Journal tab (operator-only) */}
      {activeTab === 'journal' && (
        <Box sx={{ flex: '1 1 auto', overflowY: 'auto' }}>
          <JournalPanel
            journals={journals}
            pendingResult={journalResult}
            generating={journalGenerating}
            journalError={journalError}
            rxTexts={rxTexts}
            rxCallsigns={rxCallsigns}
            onListJournals={onListJournals}
            onGenerate={onGenerate}
            onSave={onSaveJournal}
            onDelete={onDeleteJournal}
            onPublish={onPublishJournal}
            onUnpublish={onUnpublishJournal}
            onDismissResult={onDismissJournalResult}
          />
        </Box>
      )}

      <BottomNavigation
        value={activeTab}
        onChange={(_, v) => setTab(v)}
        showLabels
        aria-label="Main tabs"
        sx={{ borderTop: 1, borderColor: 'divider', flexShrink: 0 }}
      >
        <BottomNavigationAction label="Chat" value="chat" icon={<ChatIcon />} />
        <BottomNavigationAction label="Family" value="family" icon={<FamilyRestroomIcon />} />
        <BottomNavigationAction label="Neighborhood" value="neighborhood" icon={<HolidayVillageIcon />} />
        {isOperatorTier && (
          <BottomNavigationAction label="Stations" value="stations" icon={<PeopleIcon />} />
        )}
        {isOperatorTier && (
          <BottomNavigationAction label="Journal" value="journal" icon={<ArticleIcon />} />
        )}
      </BottomNavigation>

      <ContactsDialog
        open={showContacts}
        onClose={onContactsClose}
        contacts={contacts}
        prefilledCallsign={pendingPrefilledCallsign}
        prefilledName={pendingPrefilledName}
        prefilledLocation={pendingPrefilledLocation}
        fccLookupResult={fccLookupResult}
        verifyAllComplete={verifyAllComplete}
        onSend={send}
        onVerifyAllDismiss={onVerifyAllDismiss}
      />

      <Snackbar
        open={publishSnack !== null}
        autoHideDuration={5000}
        onClose={onClosePublishSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={onClosePublishSnack} severity="success" aria-live="polite" aria-atomic="true" sx={{ width: '100%' }}>
          {publishSnack}
        </Alert>
      </Snackbar>

      <Snackbar
        open={errorSnack !== null}
        autoHideDuration={7000}
        onClose={onCloseErrorSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={onCloseErrorSnack} severity="error" aria-live="assertive" aria-atomic="true" sx={{ width: '100%' }}>
          {errorSnack}
        </Alert>
      </Snackbar>

      <Snackbar
        open={journalSavedSnack !== null}
        autoHideDuration={4000}
        onClose={onCloseJournalSavedSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={onCloseJournalSavedSnack} severity="success" aria-live="polite" aria-atomic="true" sx={{ width: '100%' }}>
          {journalSavedSnack}
        </Alert>
      </Snackbar>

      <Snackbar
        open={vocabSnack !== null}
        autoHideDuration={4000}
        onClose={onCloseVocabSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={onCloseVocabSnack} severity="success" aria-live="polite" aria-atomic="true" sx={{ width: '100%' }}>
          {vocabSnack}
        </Alert>
      </Snackbar>
    </Box>
  );
}
