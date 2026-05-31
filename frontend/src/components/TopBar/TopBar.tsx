import {
  AppBar,
  Toolbar,
  Button,
  Box,
  IconButton,
  Tooltip,
} from '@mui/material';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import { AccountMenu } from '../AccountMenu/AccountMenu';
import type { UserProfile } from '../../types/ws';

interface Props {
  profile: UserProfile;
  stationStatus: string;
  connected: boolean;
  isOnline: boolean | null;
  serviceMode: string;
  listenOnly: boolean;
  showAttendance: boolean;
  onToggleAttendance: () => void;
  showJournal: boolean;
  onToggleJournal: () => void;
  showContacts: boolean;
  onToggleContacts: () => void;
  showConfig: boolean;
  onToggleConfig: () => void;
  showAdmin: boolean;
  onToggleAdmin: () => void;
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
}

export function TopBar({
  profile,
  stationStatus,
  connected,
  isOnline,
  serviceMode,
  listenOnly,
  showAttendance,
  onToggleAttendance,
  showJournal,
  onToggleJournal,
  showContacts,
  onToggleContacts,
  showConfig,
  onToggleConfig,
  showAdmin,
  onToggleAdmin,
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
}: Props) {
  return (
    <AppBar position="static" color="default" elevation={0}
      sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <Toolbar sx={{ gap: 1, flexWrap: 'wrap', py: 0.5 }}>

        {/* Account menu (replaces CHANGE OPERATOR) */}
        <AccountMenu
          profile={profile}
          onUpdateProfile={onUpdateProfile}
          onChangePassword={onChangePassword}
          onLogout={onLogout}
        />

        <Button
          variant={showAttendance ? 'contained' : 'outlined'}
          size="small"
          onClick={onToggleAttendance}
          aria-pressed={showAttendance}
          aria-label="Toggle stations heard panel"
        >
          STATIONS
        </Button>

        <Button
          variant={showJournal ? 'contained' : 'outlined'}
          size="small"
          onClick={onToggleJournal}
          aria-pressed={showJournal}
          aria-label="Toggle journal panel"
        >
          JOURNAL
        </Button>

        <Button
          variant={showContacts ? 'contained' : 'outlined'}
          size="small"
          onClick={onToggleContacts}
          aria-pressed={showContacts}
          aria-label="Open contacts"
        >
          CONTACTS
        </Button>

        <Button
          variant={showConfig ? 'contained' : 'outlined'}
          size="small"
          onClick={onToggleConfig}
          aria-pressed={showConfig}
          aria-label="Toggle configuration panel"
        >
          CONFIG
        </Button>

        {profile.is_admin && (
          <Button
            variant={showAdmin ? 'contained' : 'outlined'}
            size="small"
            onClick={onToggleAdmin}
            aria-pressed={showAdmin}
            aria-label="Open admin settings"
          >
            ADMIN
          </Button>
        )}

        {/* Center: station status + online dot */}
        <Box sx={{ flex: 1, textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }} aria-live="polite" aria-atomic="true">
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

        {/* Right: service mode, listen-only, clear chat, theme */}
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

        <Tooltip title="Clear chat log">
          <IconButton
            onClick={onClearChat}
            aria-label="Clear chat log"
            size="small"
          >
            <DeleteSweepIcon />
          </IconButton>
        </Tooltip>

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
    </AppBar>
  );
}
