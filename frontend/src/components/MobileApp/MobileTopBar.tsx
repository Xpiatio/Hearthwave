import { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Box,
  Button,
  IconButton,
  Typography,
  SwipeableDrawer,
  List,
  ListItem,
  ListItemText,
  Switch,
  Divider,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { VoicePTT } from '../VoicePTT/VoicePTT';
import { AccountMenu } from '../AccountMenu/AccountMenu';
import type { UserProfile, VoiceOption } from '../../types/ws';

interface MobileTopBarProps {
  profile: UserProfile;
  effectiveCallsign: string;
  connected: boolean;
  transmitting: boolean;
  listenOnly: boolean;
  sttListening: boolean;
  readAloud: boolean;
  notificationsEnabled: boolean;
  darkMode: boolean;
  voices: VoiceOption[];
  voicePreviewBusy: boolean;
  stationLengthScale: number;
  showConfig: boolean;
  showAdmin: boolean;
  showServerConfig: boolean;
  onToggleSttListening: () => void;
  onToggleReadAloud: () => void;
  onToggleNotifications: () => void;
  onToggleListenOnly: () => void;
  onToggleDark: () => void;
  onVoicePttStart: () => void;
  onVoicePttChunk: (b64: string) => void;
  onVoicePttEnd: () => void;
  onVoicePttCancel: () => void;
  onTxAbort: () => void;
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
  onToggleConfig: () => void;
  onToggleAdmin: () => void;
  onToggleServerConfig: () => void;
}

export function MobileTopBar({
  profile,
  effectiveCallsign,
  connected,
  transmitting,
  listenOnly,
  sttListening,
  readAloud,
  notificationsEnabled,
  darkMode,
  voices,
  voicePreviewBusy,
  stationLengthScale,
  showConfig,
  showAdmin,
  showServerConfig,
  onToggleSttListening,
  onToggleReadAloud,
  onToggleNotifications,
  onToggleListenOnly,
  onToggleDark,
  onVoicePttStart,
  onVoicePttChunk,
  onVoicePttEnd,
  onVoicePttCancel,
  onTxAbort,
  onUpdateProfile,
  onChangePassword,
  onLogout,
  onPreviewVoice,
  onSaveTtsPrefs,
  onToggleConfig,
  onToggleAdmin,
  onToggleServerConfig,
}: MobileTopBarProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <AppBar position="sticky" color="default" elevation={1}>
      <Toolbar sx={{ gap: 1 }}>
        <IconButton edge="start" onClick={() => setDrawerOpen(true)} aria-label="open menu">
          <MenuIcon />
        </IconButton>

        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }} noWrap>
            {effectiveCallsign}
          </Typography>
          <Box
            aria-label={connected ? 'connected' : 'disconnected'}
            sx={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              bgcolor: connected ? 'success.main' : 'error.main',
              flexShrink: 0,
            }}
          />
        </Box>

        <VoicePTT
          disabled={transmitting || listenOnly}
          onStart={onVoicePttStart}
          onChunk={onVoicePttChunk}
          onEnd={onVoicePttEnd}
          onCancel={onVoicePttCancel}
        />

        <Button
          color="error"
          variant="contained"
          size="large"
          disabled={!transmitting}
          onClick={onTxAbort}
          sx={{ fontWeight: 700, minWidth: 90 }}
          aria-label="Abort transmission"
        >
          ABORT TX
        </Button>
      </Toolbar>

      <SwipeableDrawer
        anchor="left"
        open={drawerOpen}
        onOpen={() => setDrawerOpen(true)}
        onClose={() => setDrawerOpen(false)}
      >
        <Box sx={{ width: 280, pt: 1 }} role="presentation">
          <List disablePadding>
            <ListItem>
              <ListItemText primary="Dark mode" />
              <Switch edge="end" checked={darkMode} onChange={onToggleDark} />
            </ListItem>
            <ListItem>
              <ListItemText primary="Listen only" />
              <Switch edge="end" checked={listenOnly} onChange={onToggleListenOnly} />
            </ListItem>
            <ListItem>
              <ListItemText primary="STT listening" />
              <Switch edge="end" checked={sttListening} onChange={onToggleSttListening} />
            </ListItem>
            <ListItem>
              <ListItemText primary="Read aloud" />
              <Switch edge="end" checked={readAloud} onChange={onToggleReadAloud} />
            </ListItem>
            <ListItem>
              <ListItemText primary="Notifications" />
              <Switch edge="end" checked={notificationsEnabled} onChange={onToggleNotifications} />
            </ListItem>
          </List>
          <Divider />
          <Box sx={{ p: 1 }}>
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
              showConfig={showConfig}
              onToggleConfig={onToggleConfig}
              showAdmin={showAdmin}
              onToggleAdmin={onToggleAdmin}
              showServerConfig={showServerConfig}
              onToggleServerConfig={onToggleServerConfig}
            />
          </Box>
        </Box>
      </SwipeableDrawer>
    </AppBar>
  );
}
