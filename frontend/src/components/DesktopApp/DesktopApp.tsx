import { useRef } from 'react';
import { DndContext, useSensors, useSensor, PointerSensor, KeyboardSensor } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { DraggablePanel } from '../DraggablePanel/DraggablePanel';
import { Box, Snackbar, Alert } from '@mui/material';
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
import { QuickMessages } from '../QuickMessages/QuickMessages';
import { ContactsDialog } from '../ContactsDialog/ContactsDialog';
import { PendingStationsBar } from '../PendingStationsBar/PendingStationsBar';
import { ConfigPanel } from '../ConfigPanel/ConfigPanel';
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
  InputDeviceOption,
  MonitorSinkOption,
  UserProfile,
  VoiceOption,
  WsMessage,
} from '../../types/ws';
import type { AdminConfig, JournalResultDraft, PendingStation } from '../../types/appTypes';

export interface DesktopAppProps {
  // Identity & connection
  profile: UserProfile;
  profiles: UserProfile[];
  connected: boolean;
  isOnline: boolean | null;
  stationStatus: string;
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

  // Config panel
  filterProfanity: boolean;
  fuzzyCallsign: boolean;
  inputDevice: string | number;
  systemMonitorSink: string;
  inputDevices: InputDeviceOption[];
  monitorSinks: MonitorSinkOption[];
  spectroColormap: 'viridis' | 'grayscale';
  spectroFreqRange: 'voice' | 'full';
  spectroTimeWindowS: number;
  onToggleProfanity: () => void;
  onToggleFuzzy: () => void;
  onInputDeviceChange: (device: string | number, sink: string) => void;
  onSpectroColormapChange: (cm: 'viridis' | 'grayscale') => void;
  onSpectroFreqRangeChange: (range: 'voice' | 'full') => void;
  onSpectroTimeWindowChange: (s: number) => void;

  // Admin / server config
  adminConfig: AdminConfig;
  serverConfig: ServerConfig;
  voices: VoiceOption[];
  voicePreviewBusy: boolean;
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
  onToggleServiceMode: () => void;
  onToggleListenOnly: () => void;
  onToggleReadAloud: () => void;
  onToggleNotifications: () => void;
  onToggleSttListening: () => void;
  onToggleDark: () => void;
  onToggleWaterfall: () => void;
  onClearChat: () => void;

  // Panel visibility
  showAttendance: boolean;
  showJournal: boolean;
  showContacts: boolean;
  showConfig: boolean;
  showAdmin: boolean;
  showServerConfig: boolean;
  showNcs: boolean;
  panelOrder: string[];
  onToggleAttendance: () => void;
  onToggleJournal: () => void;
  onToggleContacts: () => void;
  onToggleConfig: () => void;
  onToggleAdmin: () => void;
  onToggleServerConfig: () => void;
  onToggleNcs: () => void;
  onPanelDragEnd: (event: DragEndEvent) => void;
  onPanelMove: (fromIndex: number, toIndex: number) => void;

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

  // Snackbars
  publishSnack: string | null;
  errorSnack: string | null;
  journalSavedSnack: string | null;
  onClosePublishSnack: () => void;
  onCloseErrorSnack: () => void;
  onCloseJournalSavedSnack: () => void;
}

export function DesktopApp({
  profile,
  profiles,
  connected,
  isOnline,
  stationStatus,
  showCallsignChips,
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
  onStandaloneId,
  onVoicePttStart,
  onVoicePttChunk,
  onVoicePttEnd,
  onVoicePttCancel,
  onTxAbort,
  filterProfanity,
  fuzzyCallsign,
  inputDevice,
  systemMonitorSink,
  inputDevices,
  monitorSinks,
  spectroColormap,
  spectroFreqRange,
  spectroTimeWindowS,
  onToggleProfanity,
  onToggleFuzzy,
  onInputDeviceChange,
  onSpectroColormapChange,
  onSpectroFreqRangeChange,
  onSpectroTimeWindowChange,
  adminConfig,
  serverConfig,
  voices,
  voicePreviewBusy,
  onAdminSave,
  onServerConfigSave,
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
  onToggleServiceMode,
  onToggleListenOnly,
  onToggleReadAloud,
  onToggleNotifications,
  onToggleSttListening,
  onToggleDark,
  onToggleWaterfall,
  onClearChat,
  showAttendance,
  showJournal,
  showContacts,
  showConfig,
  showAdmin,
  showServerConfig,
  showNcs,
  panelOrder,
  onToggleAttendance,
  onToggleJournal,
  onToggleContacts,
  onToggleConfig,
  onToggleAdmin,
  onToggleServerConfig,
  onToggleNcs,
  onPanelDragEnd,
  onPanelMove,
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
  publishSnack,
  errorSnack,
  journalSavedSnack,
  onClosePublishSnack,
  onCloseErrorSnack,
  onCloseJournalSavedSnack,
}: DesktopAppProps) {
  const messageInputRef = useRef<MessageInputHandle>(null);
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

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
        showConfig={showConfig}
        onToggleConfig={onToggleConfig}
        showAdmin={showAdmin}
        onToggleAdmin={onToggleAdmin}
        showServerConfig={showServerConfig}
        onToggleServerConfig={onToggleServerConfig}
        showNcs={showNcs}
        onToggleNcs={onToggleNcs}
        showWaterfall={showWaterfall}
        onToggleWaterfall={onToggleWaterfall}
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
      />

      <DndContext sensors={sensors} onDragEnd={onPanelDragEnd}>
        <SortableContext items={panelOrder} strategy={verticalListSortingStrategy}>
          {panelOrder.map((id, index) => {
            if (id === 'config' && showConfig) {
              return (
                <DraggablePanel
                  key="config"
                  id="config"
                  onMoveUp={index > 0 ? () => onPanelMove(index, index - 1) : undefined}
                  onMoveDown={index < panelOrder.length - 1 ? () => onPanelMove(index, index + 1) : undefined}
                >
                  <ConfigPanel
                    filterProfanity={filterProfanity}
                    fuzzyCallsign={fuzzyCallsign}
                    inputDevice={inputDevice}
                    systemMonitorSink={systemMonitorSink}
                    inputDevices={inputDevices}
                    monitorSinks={monitorSinks}
                    spectroColormap={spectroColormap}
                    spectroFreqRange={spectroFreqRange}
                    spectroTimeWindowS={spectroTimeWindowS}
                    onToggleProfanity={onToggleProfanity}
                    onToggleFuzzy={onToggleFuzzy}
                    onInputDeviceChange={onInputDeviceChange}
                    onSpectroColormapChange={onSpectroColormapChange}
                    onSpectroFreqRangeChange={onSpectroFreqRangeChange}
                    onSpectroTimeWindowChange={onSpectroTimeWindowChange}
                  />
                </DraggablePanel>
              );
            }
            if (id === 'attendance' && showAttendance) {
              return (
                <DraggablePanel
                  key="attendance"
                  id="attendance"
                  onMoveUp={index > 0 ? () => onPanelMove(index, index - 1) : undefined}
                  onMoveDown={index < panelOrder.length - 1 ? () => onPanelMove(index, index + 1) : undefined}
                >
                  <AttendancePanel
                    stations={attendanceStations}
                    onClear={onClearAttendance}
                  />
                </DraggablePanel>
              );
            }
            if (id === 'journal' && showJournal) {
              return (
                <DraggablePanel
                  key="journal"
                  id="journal"
                  onMoveUp={index > 0 ? () => onPanelMove(index, index - 1) : undefined}
                  onMoveDown={index < panelOrder.length - 1 ? () => onPanelMove(index, index + 1) : undefined}
                >
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
                </DraggablePanel>
              );
            }
            if (id === 'ncs' && showNcs) {
              return (
                <DraggablePanel
                  key="ncs"
                  id="ncs"
                  onMoveUp={index > 0 ? () => onPanelMove(index, index - 1) : undefined}
                  onMoveDown={index < panelOrder.length - 1 ? () => onPanelMove(index, index + 1) : undefined}
                >
                  <NCSPanel
                    send={send}
                    lastMessage={lastMessage}
                    contacts={contacts}
                    channelClear={channelClear}
                    transmitting={transmitting}
                  />
                </DraggablePanel>
              );
            }
            return null;
          })}
        </SortableContext>
      </DndContext>

      <PendingStationsBar
        stations={pendingStations}
        onAdd={onAddPending}
        onDismiss={onDismissPending}
        onDismissAll={onDismissAllPending}
      />

      <Box sx={{ display: 'flex', flexDirection: 'row', flex: '1 1 auto', overflow: 'hidden' }}>
        {showWaterfall && (
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
    </Box>
  );
}
