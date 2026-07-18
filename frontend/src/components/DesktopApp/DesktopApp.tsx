import { useRef } from 'react';
import { Box, Snackbar, Alert, Dialog } from '@mui/material';
import { useEscapeToHome } from '../../hooks/useEscapeToHome';
import { TopBar } from '../TopBar/TopBar';
import { ChatDisplay } from '../ChatDisplay/ChatDisplay';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';
import { StatusRow } from '../StatusRow/StatusRow';
import { MessageInput } from '../MessageInput/MessageInput';
import type { MessageInputHandle } from '../MessageInput/MessageInput';
import { AttendancePanel } from '../AttendancePanel/AttendancePanel';
import { JournalPanel } from '../JournalPanel/JournalPanel';
import { NCSPanel } from '../NCSPanel/NCSPanel';
import { Spectrogram } from '../Spectrogram/Spectrogram';
import type { SpectrogramHandle } from '../Spectrogram/Spectrogram';
import { AudioLevelMeter } from '../AudioLevelMeter/AudioLevelMeter';
import type { AudioLevelMeterHandle } from '../AudioLevelMeter/AudioLevelMeter';
import { QuickMessages } from '../QuickMessages/QuickMessages';
import { PresetComposer } from '../FamilyPanel/PresetComposer';
import { ContactsDialog } from '../ContactsDialog/ContactsDialog';
import { PendingStationsBar } from '../PendingStationsBar/PendingStationsBar';
import type { TxComposition } from '../../plugins';
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

export interface DesktopAppProps {
  // Identity & connection
  profile: UserProfile;
  connected: boolean;
  isOnline: boolean | null;
  stationStatus: string;
  showCallsignChips: boolean;
  /** Interface tier — gates advanced/operator-only TopBar controls. */
  uiLevel: 'simple' | 'operator';
  /** Returns to the HomeScreen shell. Renders a Home button (and Escape
   *  listener) when provided; the desktop-only home routing lives in App.tsx. */
  onGoHome?: () => void;
  /** Kid accounts: no Settings entry point, and the free-text composer is
   *  replaced by a PresetComposer built from quickMessages. */
  isKid: boolean;
  quickMessages: string[];

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

  // Spectrogram display (read-only view props; config lives in SettingsDialog)
  spectroColormap: 'viridis' | 'grayscale';
  spectroTimeWindowS: number;

  // Admin / server config
  adminConfig: AdminConfig;
  voices: VoiceOption[];
  voicePreviewBusy: boolean;
  onPreviewVoice: (voiceId: string) => void;
  onSaveTtsPrefs: (prefs: { voice: string; length_scale: number }) => void;

  // Account
  onUpdateProfile: (updates: {
    operator_name?: string;
    callsign?: string;
    location?: string;
    avatar_emoji?: string;
  }) => void;
  onChangePassword: (newPassword: string) => void;
  onLogout: () => void;

  // TopBar toggles
  serviceMode: string;
  readAloud: boolean;
  notificationsEnabled: boolean;
  sttListening: boolean;
  darkMode: boolean;
  showWaterfall: boolean;
  showLevelMeter: boolean;
  onToggleServiceMode: () => void;
  onToggleListenOnly: () => void;
  onToggleReadAloud: () => void;
  onToggleNotifications: () => void;
  onToggleSttListening: () => void;
  onToggleDark: () => void;
  onToggleWaterfall: () => void;
  onToggleLevelMeter: () => void;
  onClearChat: () => void;

  // Panel visibility
  showAttendance: boolean;
  showJournal: boolean;
  showContacts: boolean;
  showNcs: boolean;
  /** Master enable state of the NCS plugin; when false its button + panel hide. */
  ncsEnabled: boolean;
  showSettings: boolean;
  onToggleAttendance: () => void;
  onToggleJournal: () => void;
  onToggleContacts: () => void;
  onToggleNcs: () => void;
  onToggleSettings: () => void;

  // Contacts dialog
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
  // Spectrogram ref (owned by App.tsx because the WS handler pushes rows to it)
  spectroRef: React.RefObject<SpectrogramHandle>;
  // RX level meter ref (owned by App.tsx; fed from the same spectrogram_row stream)
  levelMeterRef: React.RefObject<AudioLevelMeterHandle>;

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

export function DesktopApp({
  profile,
  connected,
  isOnline,
  stationStatus,
  showCallsignChips,
  uiLevel,
  onGoHome,
  isKid,
  quickMessages,
  messages,
  contacts,
  radioStatus,
  transmitting,
  lastMessage,
  channelClear,
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
  spectroColormap,
  spectroTimeWindowS,
  adminConfig,
  voices,
  voicePreviewBusy,
  onPreviewVoice,
  onSaveTtsPrefs,
  onUpdateProfile,
  onChangePassword,
  onLogout,
  serviceMode,
  readAloud,
  notificationsEnabled,
  sttListening,
  darkMode,
  showWaterfall,
  showLevelMeter,
  onToggleServiceMode,
  onToggleListenOnly,
  onToggleReadAloud,
  onToggleNotifications,
  onToggleSttListening,
  onToggleDark,
  onToggleWaterfall,
  onToggleLevelMeter,
  onClearChat,
  showAttendance,
  showJournal,
  showContacts,
  showNcs,
  ncsEnabled,
  showSettings,
  onToggleAttendance,
  onToggleJournal,
  onToggleContacts,
  onToggleNcs,
  onToggleSettings,
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
  spectroRef,
  levelMeterRef,
  publishSnack,
  errorSnack,
  journalSavedSnack,
  vocabSnack,
  onClosePublishSnack,
  onCloseErrorSnack,
  onCloseJournalSavedSnack,
  onCloseVocabSnack,
}: DesktopAppProps) {
  const messageInputRef = useRef<MessageInputHandle>(null);

  // Escape returns to the home screen (no-ops when onGoHome is undefined).
  useEscapeToHome(onGoHome);

  // Operator-only panels (waterfall, RX level meter, NCS, attendance,
  // journal) must not render in simple tier even if their show-flags are
  // still true from a prior operator-tier session — the flags persist
  // independently of uiLevel in App.tsx state, so gate rendering here too,
  // not just the TopBar toggle buttons that flip the flags.
  const isOperatorTier = uiLevel === 'operator';

  return (
    <Box
      className="app-shell"
      sx={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
    >
      <TopBar
        profile={profile}
        stationStatus={stationStatus}
        connected={connected}
        isOnline={isOnline}
        uiLevel={uiLevel}
        onGoHome={onGoHome}
        serviceMode={serviceMode}
        listenOnly={listenOnly}
        readAloud={readAloud}
        onToggleReadAloud={onToggleReadAloud}
        notificationsEnabled={notificationsEnabled}
        onToggleNotifications={onToggleNotifications}
        showAttendance={showAttendance}
        onToggleAttendance={onToggleAttendance}
        showJournal={showJournal}
        onToggleJournal={onToggleJournal}
        showContacts={showContacts}
        onToggleContacts={onToggleContacts}
        showSettings={showSettings}
        onToggleSettings={onToggleSettings}
        showNcs={showNcs}
        ncsEnabled={ncsEnabled}
        onToggleNcs={onToggleNcs}
        showWaterfall={showWaterfall}
        onToggleWaterfall={onToggleWaterfall}
        showLevelMeter={showLevelMeter}
        onToggleLevelMeter={onToggleLevelMeter}
        darkMode={darkMode}
        onToggleDark={onToggleDark}
        onToggleServiceMode={onToggleServiceMode}
        onToggleListenOnly={onToggleListenOnly}
        sttListening={sttListening}
        onToggleSttListening={onToggleSttListening}
        onClearChat={onClearChat}
        onUpdateProfile={onUpdateProfile}
        onChangePassword={onChangePassword}
        onLogout={onLogout}
        voices={voices}
        voicePreviewBusy={voicePreviewBusy}
        onPreviewVoice={onPreviewVoice}
        stationLengthScale={adminConfig.stationLengthScale}
        onSaveTtsPrefs={onSaveTtsPrefs}
        transmitting={transmitting}
        onVoicePttStart={onVoicePttStart}
        onVoicePttChunk={onVoicePttChunk}
        onVoicePttEnd={onVoicePttEnd}
        onVoicePttCancel={onVoicePttCancel}
        onTxAbort={onTxAbort}
        isKid={isKid}
      />

      {showNcs && ncsEnabled && isOperatorTier && (
        <NCSPanel send={send} lastMessage={lastMessage} contacts={contacts}
                  channelClear={channelClear} transmitting={transmitting} />
      )}

      <PendingStationsBar
        stations={pendingStations}
        onAdd={onAddPending}
        onDismiss={onDismissPending}
        onDismissAll={onDismissAllPending}
      />

      {showLevelMeter && isOperatorTier && <AudioLevelMeter ref={levelMeterRef} />}

      <Box sx={{ display: 'flex', flexDirection: 'row', flex: '1 1 auto', overflow: 'hidden' }}>
        {showWaterfall && isOperatorTier && (
          <Spectrogram
            ref={spectroRef}
            colormap={spectroColormap}
            timeWindowS={spectroTimeWindowS}
          />
        )}
        <ChatDisplay
          entries={messages}
          contacts={contacts}
          showCallsignChips={showCallsignChips}
        />
      </Box>

      <StatusRow status={radioStatus} />

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

      <Dialog
        open={showAttendance && isOperatorTier}
        onClose={onToggleAttendance}
        maxWidth="lg"
        fullWidth
        slotProps={{ paper: { sx: { height: '80vh' }, 'aria-label': 'Stations heard this session' } }}
      >
        <AttendancePanel stations={attendanceStations} onClear={onClearAttendance} fillHeight />
      </Dialog>

      <Dialog
        open={showJournal && isOperatorTier}
        onClose={onToggleJournal}
        maxWidth="lg"
        fullWidth
        slotProps={{ paper: { sx: { height: '80vh' }, 'aria-label': 'Session journal' } }}
      >
        <JournalPanel
          journals={journals} pendingResult={journalResult} generating={journalGenerating}
          journalError={journalError} rxTexts={rxTexts} rxCallsigns={rxCallsigns}
          onListJournals={onListJournals} onGenerate={onGenerate} onSave={onSaveJournal}
          onDelete={onDeleteJournal} onPublish={onPublishJournal} onUnpublish={onUnpublishJournal}
          onDismissResult={onDismissJournalResult}
          fillHeight
        />
      </Dialog>

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
        <Alert
          onClose={onClosePublishSnack}
          severity="success"
          sx={{ width: '100%' }}
          aria-live="polite"
          aria-atomic="true"
        >
          {publishSnack}
        </Alert>
      </Snackbar>

      <Snackbar
        open={errorSnack !== null}
        autoHideDuration={7000}
        onClose={onCloseErrorSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={onCloseErrorSnack}
          severity="error"
          sx={{ width: '100%' }}
          aria-live="assertive"
          aria-atomic="true"
        >
          {errorSnack}
        </Alert>
      </Snackbar>

      <Snackbar
        open={journalSavedSnack !== null}
        autoHideDuration={4000}
        onClose={onCloseJournalSavedSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={onCloseJournalSavedSnack}
          severity="success"
          sx={{ width: '100%' }}
          aria-live="polite"
          aria-atomic="true"
        >
          {journalSavedSnack}
        </Alert>
      </Snackbar>

      <Snackbar
        open={vocabSnack !== null}
        autoHideDuration={4000}
        onClose={onCloseVocabSnack}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={onCloseVocabSnack}
          severity="success"
          sx={{ width: '100%' }}
          aria-live="polite"
          aria-atomic="true"
        >
          {vocabSnack}
        </Alert>
      </Snackbar>
    </Box>
  );
}
