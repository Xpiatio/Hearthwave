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
import PhoneAndroidIcon from '@mui/icons-material/PhoneAndroid';

interface Props {
  stationStatus: string;
  connected: boolean;
  isOnline: boolean | null;
  serviceMode: string;
  listenOnly: boolean;
  onChangeOperator: () => void;
  showAttendance: boolean;
  onToggleAttendance: () => void;
  showJournal: boolean;
  onToggleJournal: () => void;
  showContacts: boolean;
  onToggleContacts: () => void;
  showConfig: boolean;
  onToggleConfig: () => void;
  darkMode: boolean;
  onToggleDark: () => void;
  touchMode: boolean;
  onToggleTouch: () => void;
  onToggleServiceMode: () => void;
  onToggleListenOnly: () => void;
}

export function TopBar({
  stationStatus,
  connected,
  isOnline,
  serviceMode,
  listenOnly,
  onChangeOperator,
  showAttendance,
  onToggleAttendance,
  showJournal,
  onToggleJournal,
  showContacts,
  onToggleContacts,
  showConfig,
  onToggleConfig,
  darkMode,
  onToggleDark,
  touchMode,
  onToggleTouch,
  onToggleServiceMode,
  onToggleListenOnly,
}: Props) {
  return (
    <AppBar position="static" color="default" elevation={0}
      sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <Toolbar sx={{ gap: 1, flexWrap: 'wrap', py: 0.5 }}>

        {/* Left: navigation buttons */}
        <Button variant="outlined" size="small" onClick={onChangeOperator}
          aria-label="Change operator profile">
          CHANGE OPERATOR
        </Button>

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

        {/* Right: service mode, listen-only, theme, touch */}
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

        <Tooltip title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}>
          <IconButton
            onClick={onToggleDark}
            aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            size="small"
          >
            {darkMode ? <Brightness7Icon /> : <Brightness4Icon />}
          </IconButton>
        </Tooltip>

        <Tooltip title={touchMode ? 'Exit touch mode' : 'Enable touch mode'}>
          <IconButton
            onClick={onToggleTouch}
            color={touchMode ? 'primary' : 'default'}
            aria-label={touchMode ? 'Exit touch mode' : 'Enable touch mode'}
            aria-pressed={touchMode}
            size="small"
          >
            <PhoneAndroidIcon />
          </IconButton>
        </Tooltip>
      </Toolbar>
    </AppBar>
  );
}
