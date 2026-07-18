import { useState } from 'react';
import {
  AppBar,
  Toolbar,
  ToggleButton,
  Button,
  Box,
  Divider,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import HomeIcon from '@mui/icons-material/Home';
import { AccountMenu } from '../AccountMenu/AccountMenu';
import { VoicePTT } from '../VoicePTT/VoicePTT';
import { Logo } from '../Logo/Logo';
import { AboutDialog } from '../AboutDialog/AboutDialog';
import type { UserProfile, VoiceOption } from '../../types/ws';

interface Props {
  profile: UserProfile;
  stationStatus: string;
  connected: boolean;
  isOnline: boolean | null;
  /** Interface tier — gates advanced/operator-only controls when 'simple'. */
  uiLevel: 'simple' | 'operator';
  /** Returns to the HomeScreen shell; renders a Home button first when provided. */
  onGoHome?: () => void;
  /** Kid accounts have no settings surface — hides the Settings menu item. */
  isKid: boolean;
  serviceMode: string;
  listenOnly: boolean;
  readAloud: boolean;
  onToggleReadAloud: () => void;
  notificationsEnabled: boolean;
  onToggleNotifications: () => void;
  showAttendance: boolean;
  onToggleAttendance: () => void;
  showJournal: boolean;
  onToggleJournal: () => void;
  showContacts: boolean;
  onToggleContacts: () => void;
  showSettings: boolean;
  onToggleSettings: () => void;
  showNcs: boolean;
  /** Master enable state of the NCS plugin; when false the NCS button hides. */
  ncsEnabled: boolean;
  onToggleNcs: () => void;
  showWaterfall: boolean;
  onToggleWaterfall: () => void;
  showLevelMeter: boolean;
  onToggleLevelMeter: () => void;
  darkMode: boolean;
  onToggleDark: () => void;
  onToggleServiceMode: () => void;
  onToggleListenOnly: () => void;
  sttListening: boolean;
  onToggleSttListening: () => void;
  onClearChat: () => void;
  onUpdateProfile: (updates: {
    operator_name?: string;
    callsign?: string;
    location?: string;
    avatar_emoji?: string;
  }) => void;
  onChangePassword: (newPassword: string) => void;
  onLogout: () => void;
  voices: VoiceOption[];
  voicePreviewBusy: boolean;
  onPreviewVoice: (voiceId: string) => void;
  stationLengthScale: number;
  onSaveTtsPrefs: (prefs: { voice: string; length_scale: number }) => void;
  transmitting: boolean;
  onVoicePttStart: () => void;
  onVoicePttChunk: (b64: string) => void;
  onVoicePttEnd: () => void;
  onVoicePttCancel: () => void;
  onTxAbort: () => void;
}

export function TopBar({
  profile,
  stationStatus,
  connected,
  isOnline,
  uiLevel,
  onGoHome,
  isKid,
  serviceMode,
  listenOnly,
  readAloud,
  onToggleReadAloud,
  notificationsEnabled,
  onToggleNotifications,
  showAttendance,
  onToggleAttendance,
  showJournal,
  onToggleJournal,
  showContacts,
  onToggleContacts,
  showSettings,
  onToggleSettings,
  showNcs,
  ncsEnabled,
  onToggleNcs,
  showWaterfall,
  onToggleWaterfall,
  showLevelMeter,
  onToggleLevelMeter,
  darkMode,
  onToggleDark,
  onToggleServiceMode,
  onToggleListenOnly,
  sttListening,
  onToggleSttListening,
  onClearChat,
  onUpdateProfile,
  onChangePassword,
  onLogout,
  voices,
  voicePreviewBusy,
  onPreviewVoice,
  stationLengthScale,
  onSaveTtsPrefs,
  transmitting,
  onVoicePttStart,
  onVoicePttChunk,
  onVoicePttEnd,
  onVoicePttCancel,
  onTxAbort,
}: Props) {
  const [aboutOpen, setAboutOpen] = useState(false);
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  return (
    <AppBar position="static" color="default" elevation={0}
      sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <Toolbar sx={{ gap: 1, flexWrap: 'wrap', py: 0.5 }}>

        {onGoHome && (
          <Tooltip title="Home screen">
            <IconButton aria-label="Home screen" onClick={onGoHome} size="small">
              <HomeIcon />
            </IconButton>
          </Tooltip>
        )}

        {/* Brand — click to open About */}
        <Tooltip title="About Hearthwave">
          <IconButton
            onClick={() => setAboutOpen(true)}
            aria-label="About Hearthwave"
            size="small"
            sx={{ p: 0.5 }}
          >
            <Logo size={28} />
          </IconButton>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

        {/* Group 1 — Identity */}
        <AccountMenu
          profile={profile}
          onUpdateProfile={onUpdateProfile}
          onChangePassword={onChangePassword}
          onLogout={onLogout}
          voices={voices}
          voicePreviewBusy={voicePreviewBusy}
          onPreviewVoice={onPreviewVoice}
          stationLengthScale={stationLengthScale}
          onSaveTtsPrefs={onSaveTtsPrefs}
          showSettings={showSettings}
          onToggleSettings={onToggleSettings}
          isKid={isKid}
        />

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

        {/* Group 2 — Panel toggles. Advanced panels are operator-tier only. */}
        {uiLevel === 'operator' && (
          <ToggleButton
            value="attendance"
            selected={showAttendance}
            onClick={onToggleAttendance}
            size="small"
            color="primary"
            aria-label="Toggle stations heard panel"
          >
            STATIONS
          </ToggleButton>
        )}

        {uiLevel === 'operator' && (
          <ToggleButton
            value="journal"
            selected={showJournal}
            onClick={onToggleJournal}
            size="small"
            color="primary"
            aria-label="Toggle journal panel"
          >
            JOURNAL
          </ToggleButton>
        )}

        <ToggleButton
          value="contacts"
          selected={showContacts}
          onClick={onToggleContacts}
          size="small"
          color="primary"
          aria-label="Toggle contacts"
        >
          CONTACTS
        </ToggleButton>

        {uiLevel === 'operator' && (
          <ToggleButton
            value="waterfall"
            selected={showWaterfall}
            onClick={onToggleWaterfall}
            size="small"
            color="primary"
            aria-label={showWaterfall ? 'Hide waterfall' : 'Show waterfall'}
          >
            WATERFALL
          </ToggleButton>
        )}

        {uiLevel === 'operator' && (
          <ToggleButton
            value="levelmeter"
            selected={showLevelMeter}
            onClick={onToggleLevelMeter}
            size="small"
            color="primary"
            aria-label={showLevelMeter ? 'Hide audio level meter' : 'Show audio level meter'}
          >
            LEVEL
          </ToggleButton>
        )}

        {uiLevel === 'operator' && profile.is_admin && ncsEnabled && (
          <Tooltip title={showNcs ? 'Hide Net Control Station panel' : 'Show Net Control Station panel'}>
            <ToggleButton
              value="ncs"
              selected={showNcs}
              onClick={onToggleNcs}
              size="small"
              color="error"
              aria-label={showNcs ? 'NCS panel visible — click to hide' : 'Show NCS panel'}
            >
              NCS MODE
            </ToggleButton>
          </Tooltip>
        )}

        {/* Center — station status + FCC online dot */}
        <Box
          sx={{ flex: 1, textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}
          aria-live="polite"
          aria-atomic="true"
        >
          <Box component="span" sx={{ typography: 'body1', fontWeight: 600 }}>
            STATION STATUS:{' '}
          </Box>
          <Box
            component="span"
            sx={{
              typography: 'body1',
              fontWeight: 700,
              color: connected ? 'primary.main' : 'warning.main',
            }}
          >
            {connected ? stationStatus : 'OFFLINE'}
          </Box>
          {isOnline !== null && (
            <Tooltip title={isOnline ? 'FCC lookup: online' : 'FCC lookup: offline'}>
              <Box
                component="span"
                role="img"
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  bgcolor: isOnline ? 'success.main' : 'text.disabled',
                  display: 'inline-block',
                  flexShrink: 0,
                }}
                aria-label={isOnline ? 'FCC lookup online' : 'FCC lookup offline'}
              />
            </Tooltip>
          )}
        </Box>

        {/* Group 3 — Radio operation controls */}
        {uiLevel === 'operator' && (
          <Tooltip title={`Radio service: click to switch to ${serviceMode === 'GMRS' ? 'FRS' : 'GMRS'}`}>
            <Button
              variant="outlined"
              size="small"
              onClick={onToggleServiceMode}
              aria-label={`Service mode: ${serviceMode}. Click to switch.`}
              sx={{ fontFamily: 'monospace', fontWeight: 700, minWidth: 56 }}
            >
              {serviceMode}
            </Button>
          </Tooltip>
        )}

        {uiLevel === 'operator' && (
          <Tooltip title={sttListening ? 'STT active — click to stop listening' : 'STT stopped — click to start listening'}>
            <Button
              variant={sttListening ? 'contained' : 'outlined'}
              color={sttListening ? 'success' : 'inherit'}
              size="small"
              onClick={onToggleSttListening}
              aria-pressed={sttListening}
              aria-label={sttListening ? 'Listening active — click to stop' : 'Listening stopped — click to start'}
            >
              {sttListening ? 'LISTENING' : 'LISTEN'}
            </Button>
          </Tooltip>
        )}

        {/* Listen-only is server-enforced off for kid accounts (I5) — a kid
            toggling it themselves would defeat that lock, so hide it. */}
        {!isKid && (
          <Tooltip title={listenOnly ? 'Listen-only mode — click to enable TX' : 'TX enabled — click for listen-only'}>
            <Button
              variant={listenOnly ? 'contained' : 'outlined'}
              color={listenOnly ? 'warning' : 'inherit'}
              size="small"
              onClick={onToggleListenOnly}
              aria-pressed={listenOnly}
              aria-label={listenOnly ? 'Listen-only mode active — click to enable transmit' : 'Transmit enabled — click for listen-only'}
            >
              {listenOnly ? 'LISTEN ONLY' : 'TX ENABLED'}
            </Button>
          </Tooltip>
        )}

        <Tooltip title={readAloud ? 'Read aloud on — incoming messages spoken aloud' : 'Read aloud off — click to hear incoming messages'}>
          <Button
            variant={readAloud ? 'contained' : 'outlined'}
            color={readAloud ? 'info' : 'inherit'}
            size="small"
            onClick={onToggleReadAloud}
            aria-pressed={readAloud}
            aria-label={readAloud ? 'Read aloud active — click to disable' : 'Read aloud disabled — click to enable'}
          >
            READ ALOUD
          </Button>
        </Tooltip>

        <Tooltip title={notificationsEnabled ? 'Notifications on — click to disable' : 'Notifications off — click to enable (browser permission required)'}>
          <Button
            variant={notificationsEnabled ? 'contained' : 'outlined'}
            color={notificationsEnabled ? 'info' : 'inherit'}
            size="small"
            onClick={onToggleNotifications}
            aria-pressed={notificationsEnabled}
            aria-label={notificationsEnabled ? 'Notifications active — click to disable' : 'Notifications disabled — click to enable'}
          >
            NOTIFY
          </Button>
        </Tooltip>

        {/* Server rejects voice_tx_start/voice_tx_end for kid accounts (C1) —
            hide rather than disable so a kid never sees a button that would
            record audio and then error on release. */}
        {!isKid && (
          <VoicePTT
            disabled={listenOnly || transmitting || !connected}
            onStart={onVoicePttStart}
            onChunk={onVoicePttChunk}
            onEnd={onVoicePttEnd}
            onCancel={onVoicePttCancel}
          />
        )}

        <Tooltip title={transmitting ? 'Abort current transmission immediately' : 'No active transmission'}>
          <span>
            <Button
              color="error"
              variant="contained"
              size="small"
              disabled={!transmitting}
              onClick={onTxAbort}
              sx={{ fontWeight: 700, minWidth: 90 }}
              aria-label="Abort transmission"
            >
              ABORT TX
            </Button>
          </span>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

        {/* Group 4 — UI utilities. Clearing the chat is admin-only, global, and operator-tier. */}
        {uiLevel === 'operator' && profile.is_admin && (
          <Tooltip title="Clear chat log for everyone">
            <IconButton
              onClick={() => setConfirmClearOpen(true)}
              aria-label="Clear chat log"
              size="small"
            >
              <DeleteSweepIcon />
            </IconButton>
          </Tooltip>
        )}

        <Tooltip title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}>
          <IconButton
            onClick={onToggleDark}
            aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            size="small"
          >
            {darkMode ? <Brightness7Icon /> : <Brightness4Icon />}
          </IconButton>
        </Tooltip>
      </Toolbar>
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <Dialog open={confirmClearOpen} onClose={() => setConfirmClearOpen(false)}>
        <DialogTitle>Clear chat for everyone?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This wipes the shared chat log for all connected operators — base
            station, web, and mobile. This cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmClearOpen(false)}>Cancel</Button>
          <Button
            color="error"
            onClick={() => {
              setConfirmClearOpen(false);
              onClearChat();
            }}
          >
            Clear for everyone
          </Button>
        </DialogActions>
      </Dialog>
    </AppBar>
  );
}
