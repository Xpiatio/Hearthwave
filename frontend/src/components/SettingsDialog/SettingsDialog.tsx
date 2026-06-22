import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, Tabs, Tab, Box, Snackbar, Alert,
  useMediaQuery, useTheme,
} from '@mui/material';
import { ConfigPanel } from '../ConfigPanel/ConfigPanel';
import { AdminPanel, type AdminPanelHandle } from '../AdminPanel/AdminPanel';
import { ServerConfigPanel, type ServerConfigPanelHandle } from '../ServerConfigPanel/ServerConfigPanel';
import type { InputDeviceOption, MonitorSinkOption, OutputDeviceOption } from '../../types/ws';

interface Props {
  open: boolean;
  onClose: () => void;
  isAdmin: boolean;

  // Preferences tab (per-user, applied on Save)
  filterProfanity: boolean;
  fuzzyCallsign: boolean;
  inputDevice: string | number;
  systemMonitorSink: string;
  inputDevices: InputDeviceOption[];
  monitorSinks: MonitorSinkOption[];
  outputDevice: number;
  outputDevices: OutputDeviceOption[];
  spectroColormap: 'viridis' | 'grayscale';
  spectroFreqRange: 'voice' | 'full';
  spectroTimeWindowS: number;
  onToggleProfanity: () => void;
  onToggleFuzzy: () => void;
  onInputDeviceChange: (device: string | number, sink: string) => void;
  onOutputDeviceChange: (device: number) => void;
  onSpectroColormapChange: (cm: 'viridis' | 'grayscale') => void;
  onSpectroFreqRangeChange: (range: 'voice' | 'full') => void;
  onSpectroTimeWindowChange: (s: number) => void;

  // Station tab (admin only)
  adminConfig: React.ComponentProps<typeof AdminPanel>['config'];
  voices: React.ComponentProps<typeof AdminPanel>['voices'];
  voicePreviewBusy: boolean;
  onAdminSave: React.ComponentProps<typeof AdminPanel>['onSave'];
  onPreviewVoice: React.ComponentProps<typeof AdminPanel>['onPreviewVoice'];
  usersPanel?: React.ReactNode;

  // System tab (admin only)
  serverConfig: React.ComponentProps<typeof ServerConfigPanel>['config'];
  onServerConfigSave: React.ComponentProps<typeof ServerConfigPanel>['onSave'];
  onRescanVocabulary?: () => void;
}

interface PrefsDraft {
  filterProfanity: boolean; fuzzyCallsign: boolean; inputDevice: string | number;
  systemMonitorSink: string; outputDevice: number;
  spectroColormap: 'viridis' | 'grayscale'; spectroFreqRange: 'voice' | 'full'; spectroTimeWindowS: number;
}

export function SettingsDialog(props: Props) {
  const { open, onClose, isAdmin } = props;
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [tab, setTab] = useState(0);
  const [saved, setSaved] = useState(false);

  const adminRef = useRef<AdminPanelHandle>(null);
  const serverRef = useRef<ServerConfigPanelHandle>(null);
  const [adminDirty, setAdminDirty] = useState(false);
  const [serverDirty, setServerDirty] = useState(false);

  // Preferences draft, (re)seeded each time the dialog opens.
  const seedPrefs = (): PrefsDraft => ({
    filterProfanity: props.filterProfanity, fuzzyCallsign: props.fuzzyCallsign,
    inputDevice: props.inputDevice, systemMonitorSink: props.systemMonitorSink,
    outputDevice: props.outputDevice, spectroColormap: props.spectroColormap,
    spectroFreqRange: props.spectroFreqRange, spectroTimeWindowS: props.spectroTimeWindowS,
  });
  const [draft, setDraft] = useState<PrefsDraft>(seedPrefs);
  const [prefsSeed, setPrefsSeed] = useState<PrefsDraft>(seedPrefs);

  useEffect(() => {
    if (open) {
      const s = seedPrefs();
      setDraft(s); setPrefsSeed(s); setTab(0); setAdminDirty(false); setServerDirty(false);
      setSaved(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const prefsDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(prefsSeed),
    [draft, prefsSeed],
  );
  const dirty = prefsDirty || (isAdmin && (adminDirty || serverDirty));

  function applyPrefs() {
    if (draft.filterProfanity !== prefsSeed.filterProfanity) props.onToggleProfanity();
    if (draft.fuzzyCallsign !== prefsSeed.fuzzyCallsign) props.onToggleFuzzy();
    if (draft.inputDevice !== prefsSeed.inputDevice || draft.systemMonitorSink !== prefsSeed.systemMonitorSink)
      props.onInputDeviceChange(draft.inputDevice, draft.systemMonitorSink);
    if (draft.outputDevice !== prefsSeed.outputDevice) props.onOutputDeviceChange(draft.outputDevice);
    if (draft.spectroColormap !== prefsSeed.spectroColormap) props.onSpectroColormapChange(draft.spectroColormap);
    if (draft.spectroFreqRange !== prefsSeed.spectroFreqRange) props.onSpectroFreqRangeChange(draft.spectroFreqRange);
    if (draft.spectroTimeWindowS !== prefsSeed.spectroTimeWindowS) props.onSpectroTimeWindowChange(draft.spectroTimeWindowS);
  }

  function handleSave() {
    if (prefsDirty) { applyPrefs(); setPrefsSeed(draft); }
    if (isAdmin && adminDirty) { adminRef.current?.save(); setAdminDirty(false); }
    if (isAdmin && serverDirty) { serverRef.current?.save(); setServerDirty(false); }
    setSaved(true);
  }

  function handleClose() {
    if (dirty && !window.confirm('Discard unsaved changes?')) return;
    onClose();
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth fullScreen={fullScreen}>
      <DialogTitle sx={{ fontWeight: 700, pb: 0 }}>Settings</DialogTitle>

      {isAdmin && (
        <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" allowScrollButtonsMobile
              sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }} aria-label="Settings sections">
          <Tab label="Preferences" />
          <Tab label="Station" />
          <Tab label="System" />
        </Tabs>
      )}

      <DialogContent dividers>
        <Box role="tabpanel" hidden={isAdmin && tab !== 0}>
          <ConfigPanel
            hideHeader
            filterProfanity={draft.filterProfanity}
            fuzzyCallsign={draft.fuzzyCallsign}
            inputDevice={draft.inputDevice}
            systemMonitorSink={draft.systemMonitorSink}
            inputDevices={props.inputDevices}
            monitorSinks={props.monitorSinks}
            outputDevice={draft.outputDevice}
            outputDevices={props.outputDevices}
            spectroColormap={draft.spectroColormap}
            spectroFreqRange={draft.spectroFreqRange}
            spectroTimeWindowS={draft.spectroTimeWindowS}
            onToggleProfanity={() => setDraft((d) => ({ ...d, filterProfanity: !d.filterProfanity }))}
            onToggleFuzzy={() => setDraft((d) => ({ ...d, fuzzyCallsign: !d.fuzzyCallsign }))}
            onInputDeviceChange={(device, sink) => setDraft((d) => ({ ...d, inputDevice: device, systemMonitorSink: sink }))}
            onOutputDeviceChange={(device) => setDraft((d) => ({ ...d, outputDevice: device }))}
            onSpectroColormapChange={(cm) => setDraft((d) => ({ ...d, spectroColormap: cm }))}
            onSpectroFreqRangeChange={(range) => setDraft((d) => ({ ...d, spectroFreqRange: range }))}
            onSpectroTimeWindowChange={(s) => setDraft((d) => ({ ...d, spectroTimeWindowS: s }))}
          />
        </Box>

        {isAdmin && (
          <Box role="tabpanel" hidden={tab !== 1}>
            <AdminPanel
              ref={adminRef} embedded hideSaveButton open={open} onClose={onClose}
              config={props.adminConfig} voices={props.voices} voicePreviewBusy={props.voicePreviewBusy}
              onSave={props.onAdminSave} onPreviewVoice={props.onPreviewVoice}
              onDirtyChange={setAdminDirty}
            >
              {props.usersPanel}
            </AdminPanel>
          </Box>
        )}

        {isAdmin && (
          <Box role="tabpanel" hidden={tab !== 2}>
            <ServerConfigPanel
              ref={serverRef} embedded hideSaveButton open={open} onClose={onClose}
              config={props.serverConfig} onSave={props.onServerConfigSave}
              onRescanVocabulary={props.onRescanVocabulary} onDirtyChange={setServerDirty}
            />
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleSave} variant="contained" disabled={!dirty}>Save</Button>
        <Button onClick={handleClose} variant="outlined">Close</Button>
      </DialogActions>

      <Snackbar open={saved} autoHideDuration={2500} onClose={() => setSaved(false)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="success" variant="filled" onClose={() => setSaved(false)}>Settings saved</Alert>
      </Snackbar>
    </Dialog>
  );
}
