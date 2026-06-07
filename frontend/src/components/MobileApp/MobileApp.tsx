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
import { MobileTopBar } from './MobileTopBar';
import { ChatDisplay } from '../ChatDisplay/ChatDisplay';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';
import { MessageInput } from '../MessageInput/MessageInput';
import type { MessageInputHandle } from '../MessageInput/MessageInput';
import { QuickMessages } from '../QuickMessages/QuickMessages';
import { AttendancePanel } from '../AttendancePanel/AttendancePanel';
import { JournalPanel } from '../JournalPanel/JournalPanel';
import { PendingStationsBar } from '../PendingStationsBar/PendingStationsBar';
import { ContactsDialog } from '../ContactsDialog/ContactsDialog';
import { AdminPanel } from '../AdminPanel/AdminPanel';
import { ServerConfigPanel } from '../ServerConfigPanel/ServerConfigPanel';
import type { ServerConfig } from '../ServerConfigPanel/ServerConfigPanel';
import { UsersPanel } from '../UsersPanel/UsersPanel';
import type {
  StatusMsg,
  Contact,
  AttendanceStation,
  JournalEntry,
  FccLookupResultMsg,
  UserProfile,
  VoiceOption,
  WsMessage,
} from '../../types/ws';
import type { AdminConfig, JournalResultDraft, PendingStation } from '../../types/appTypes';

export interface MobileAppProps {
  // Identity & connection
  profile: UserProfile;
  profiles: UserProfile[];
  effectiveCallsign: string;
  connected: boolean;
  isOnline: boolean | null;
  showCallsignChips: boolean;

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
  onStandaloneId: () => void;
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
  serverConfig: ServerConfig;
  showConfig: boolean;
  showAdmin: boolean;
  showServerConfig: boolean;
  onToggleConfig: () => void;
  onToggleAdmin: () => void;
  onToggleServerConfig: () => void;
  onAdminSave: (values: {
    callsign: string;
    name: string;
    location: string;
    voice: string;
    tts_length_scale: number;
    gemini_api_key: string;
    journals_dir: string;
    ncs_zone: string;
    rx_mode: string;
  }) => void;
  onServerConfigSave: (values: {
    vad_threshold: number;
    whisper_model: string;
    ptt_mode: string;
    ptt_serial_port: string;
    ptt_serial_line: string;
    monitor_passthrough: boolean;
    attendance_enabled: boolean;
  }) => void;

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
  onEnrollCluster: (clusterLabel: string, callsign: string) => void;

  // Snackbars
  publishSnack: string | null;
  errorSnack: string | null;
  onClosePublishSnack: () => void;
  onCloseErrorSnack: () => void;
}

export function MobileApp({
  profile,
  profiles,
  effectiveCallsign,
  connected,
  showCallsignChips,
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
  onStandaloneId,
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
  serverConfig,
  showConfig,
  showAdmin,
  showServerConfig,
  onToggleConfig,
  onToggleAdmin,
  onToggleServerConfig,
  onAdminSave,
  onServerConfigSave,
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
  onEnrollCluster,
  publishSnack,
  errorSnack,
  onClosePublishSnack,
  onCloseErrorSnack,
}: MobileAppProps) {
  const [tab, setTab] = useState(0);
  const messageInputRef = useRef<MessageInputHandle>(null);

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
        showConfig={showConfig}
        showAdmin={showAdmin}
        showServerConfig={showServerConfig}
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
        onToggleConfig={onToggleConfig}
        onToggleAdmin={onToggleAdmin}
        onToggleServerConfig={onToggleServerConfig}
      />

      <PendingStationsBar
        stations={pendingStations}
        onAdd={onAddPending}
        onDismiss={onDismissPending}
        onDismissAll={onDismissAllPending}
      />

      {/* Chat tab */}
      {tab === 0 && (
        <Box sx={{ flex: '1 1 auto', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <ChatDisplay
            entries={messages}
            contacts={contacts}
            showCallsignChips={showCallsignChips}
            onEnrollCluster={onEnrollCluster}
          />
          {!listenOnly && (
            <QuickMessages
              operatorName={profile.operator_name}
              onSelect={(text) => messageInputRef.current?.setText(text)}
            />
          )}
          {!listenOnly && (
            <MessageInput
              ref={messageInputRef}
              transmitting={transmitting}
              contacts={contacts}
              onSend={onSend}
              onStandaloneId={onStandaloneId}
            />
          )}
        </Box>
      )}

      {/* Stations tab */}
      {tab === 1 && (
        <Box sx={{ flex: '1 1 auto', overflowY: 'auto' }}>
          <AttendancePanel
            stations={attendanceStations}
            onClear={onClearAttendance}
          />
        </Box>
      )}

      {/* Journal tab */}
      {tab === 2 && (
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
        value={tab}
        onChange={(_, v) => setTab(v)}
        showLabels
        sx={{ borderTop: 1, borderColor: 'divider', flexShrink: 0 }}
      >
        <BottomNavigationAction label="Chat" icon={<ChatIcon />} />
        <BottomNavigationAction label="Stations" icon={<PeopleIcon />} />
        <BottomNavigationAction label="Journal" icon={<ArticleIcon />} />
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

      <AdminPanel
        open={showAdmin}
        onClose={onToggleAdmin}
        config={adminConfig}
        voices={voices}
        voicePreviewBusy={voicePreviewBusy}
        onSave={onAdminSave}
        onPreviewVoice={onPreviewVoice}
      >
        {profile.is_admin && (
          <UsersPanel
            profiles={profiles}
            currentUserId={profile.id}
            onCreateProfile={(data) => send({ type: 'create_profile', ...data })}
            onDeleteProfile={(userId) => send({ type: 'delete_profile', user_id: userId })}
            onResetLockout={(userId) => send({ type: 'reset_lockout', user_id: userId })}
          />
        )}
      </AdminPanel>

      <ServerConfigPanel
        open={showServerConfig}
        onClose={onToggleServerConfig}
        config={serverConfig}
        onSave={onServerConfigSave}
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
    </Box>
  );
}
