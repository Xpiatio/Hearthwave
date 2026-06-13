import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tabs,
  Tab,
  Box,
} from '@mui/material';
import { AdminPanel } from '../AdminPanel/AdminPanel';
import { ServerConfigPanel } from '../ServerConfigPanel/ServerConfigPanel';

// Reuse the panels' own prop shapes so this stays in sync without re-declaring
// the (locally-defined) config/save value types.
type AdminProps = React.ComponentProps<typeof AdminPanel>;
type ServerProps = React.ComponentProps<typeof ServerConfigPanel>;

interface Props {
  open: boolean;
  onClose: () => void;
  // Station tab (AdminPanel)
  adminConfig: AdminProps['config'];
  voices: AdminProps['voices'];
  voicePreviewBusy: boolean;
  onAdminSave: AdminProps['onSave'];
  onPreviewVoice: AdminProps['onPreviewVoice'];
  usersPanel?: React.ReactNode;
  // System tab (ServerConfigPanel)
  serverConfig: ServerProps['config'];
  onServerConfigSave: ServerProps['onSave'];
}

/**
 * One admin dialog hosting the former "Admin" and "Server Config" panels as
 * two tabs — Station (identity/policy) and System (tuning/hardware). Each tab
 * keeps its own Save button because the two save to different backend handlers
 * (set_admin_config vs set_server_config) with different restart side-effects.
 */
export function SettingsDialog({
  open,
  onClose,
  adminConfig,
  voices,
  voicePreviewBusy,
  onAdminSave,
  onPreviewVoice,
  usersPanel,
  serverConfig,
  onServerConfigSave,
}: Props) {
  const [tab, setTab] = useState(0);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, pb: 0 }}>Admin Settings</DialogTitle>

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }}
        aria-label="Settings sections"
      >
        <Tab label="Station" id="settings-tab-station" aria-controls="settings-panel-station" />
        <Tab label="System" id="settings-tab-system" aria-controls="settings-panel-system" />
      </Tabs>

      <DialogContent dividers>
        {/* Both panels stay mounted so unsaved edits survive a tab switch. */}
        <Box role="tabpanel" id="settings-panel-station" hidden={tab !== 0}>
          <AdminPanel
            embedded
            open={open}
            onClose={onClose}
            config={adminConfig}
            voices={voices}
            voicePreviewBusy={voicePreviewBusy}
            onSave={onAdminSave}
            onPreviewVoice={onPreviewVoice}
          >
            {usersPanel}
          </AdminPanel>
        </Box>
        <Box role="tabpanel" id="settings-panel-system" hidden={tab !== 1}>
          <ServerConfigPanel
            embedded
            open={open}
            onClose={onClose}
            config={serverConfig}
            onSave={onServerConfigSave}
          />
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} variant="outlined">Close</Button>
      </DialogActions>
    </Dialog>
  );
}
