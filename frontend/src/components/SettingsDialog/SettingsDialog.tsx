import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, Tabs, Tab, Box, Snackbar, Alert,
  useMediaQuery, useTheme,
} from '@mui/material';
import { ConfigPanel } from '../ConfigPanel/ConfigPanel';
import { AdminPanel, type AdminPanelHandle } from '../AdminPanel/AdminPanel';
import { ServerConfigPanel, type ServerConfigPanelHandle } from '../ServerConfigPanel/ServerConfigPanel';
import { PluginsPanel, type PluginDraft } from '../PluginsPanel/PluginsPanel';
import { ConfirmDialog } from '../ConfirmDialog';
import type { InputDeviceOption, MonitorSinkOption, OutputDeviceOption, PluginManifest, DeviceTokenRecord } from '../../types/ws';

interface Props {
  open: boolean;
  onClose: () => void;
  isAdmin: boolean;

  // Preferences tab (per-user, applied on Save)
  filterProfanity: boolean;
  aacMode: boolean;
  fuzzyCallsign: boolean;
  fuzzyCallsignRewrite: boolean;
  inputDevice: string | number;
  systemMonitorSink: string;
  inputDevices: InputDeviceOption[];
  monitorSinks: MonitorSinkOption[];
  outputDevice: number;
  outputDevices: OutputDeviceOption[];
  spectroColormap: 'viridis' | 'grayscale';
  spectroFreqRange: 'voice' | 'full';
  spectroTimeWindowS: number;
  uiLevel: 'simple' | 'operator';
  fontScale: number;
  highContrast: boolean;
  switchScan: boolean;
  switchScanIntervalS: number;
  visualAlerts: boolean;
  onToggleProfanity: () => void;
  onToggleAacMode: () => void;
  onToggleFuzzy: () => void;
  onToggleFuzzyRewrite: () => void;
  onInputDeviceChange: (device: string | number, sink: string) => void;
  onOutputDeviceChange: (device: number) => void;
  onSpectroColormapChange: (cm: 'viridis' | 'grayscale') => void;
  onSpectroFreqRangeChange: (range: 'voice' | 'full') => void;
  onSpectroTimeWindowChange: (s: number) => void;
  onUiLevelChange: (v: 'simple' | 'operator') => void;
  onFontScaleChange: (v: number) => void;
  onToggleHighContrast: () => void;
  onToggleSwitchScan: () => void;
  onSwitchScanIntervalChange: (v: number) => void;
  onToggleVisualAlerts: () => void;

  // Station tab (admin only)
  adminConfig: React.ComponentProps<typeof AdminPanel>['config'];
  voices: React.ComponentProps<typeof AdminPanel>['voices'];
  voicePreviewBusy: boolean;
  onAdminSave: React.ComponentProps<typeof AdminPanel>['onSave'];
  onPreviewVoice: React.ComponentProps<typeof AdminPanel>['onPreviewVoice'];
  usersPanel?: React.ReactNode;
  deviceTokens: DeviceTokenRecord[];
  createdToken: DeviceTokenRecord | null;
  onCreateDeviceToken: (label: string) => void;
  onRevokeDeviceToken: (id: string) => void;

  // System tab (admin only)
  serverConfig: React.ComponentProps<typeof ServerConfigPanel>['config'];
  onServerConfigSave: React.ComponentProps<typeof ServerConfigPanel>['onSave'];
  onRescanVocabulary?: () => void;
  onOpenCalibration?: () => void;

  // Plugins tab (admin only)
  plugins: PluginManifest[];
  /** Persist plugin enable + config drafts (namespaced by plugin id). */
  onPluginsSave: (draft: PluginDraft) => void;
  /** Install a plugin from an uploaded .zip (immediate). */
  onInstallPlugin?: (file: File) => void;
  /** Reload a plugin from disk. */
  onReloadPlugin?: (id: string) => void;
  /** Uninstall a plugin. */
  onUninstallPlugin?: (id: string) => void;
  /** True while a plugin install/reload/uninstall request is in flight. */
  pluginBusy?: boolean;
}

interface PrefsDraft {
  filterProfanity: boolean; aacMode: boolean; fuzzyCallsign: boolean; fuzzyCallsignRewrite: boolean; inputDevice: string | number;
  systemMonitorSink: string; outputDevice: number;
  spectroColormap: 'viridis' | 'grayscale'; spectroFreqRange: 'voice' | 'full'; spectroTimeWindowS: number;
  uiLevel: 'simple' | 'operator'; fontScale: number; highContrast: boolean;
  switchScan: boolean; switchScanIntervalS: number; visualAlerts: boolean;
}

export function SettingsDialog(props: Props) {
  const { open, onClose, isAdmin } = props;
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [tab, setTab] = useState(0);
  const [saved, setSaved] = useState(false);
  const [discardConfirmOpen, setDiscardConfirmOpen] = useState(false);

  const adminRef = useRef<AdminPanelHandle>(null);
  const serverRef = useRef<ServerConfigPanelHandle>(null);
  const [adminDirty, setAdminDirty] = useState(false);
  const [serverDirty, setServerDirty] = useState(false);

  // Plugins tab draft — { [pluginId]: { enabled, ...configValues } }, seeded from
  // each plugin's broadcast enabled state + current config values.
  const seedPlugins = (): PluginDraft =>
    Object.fromEntries(props.plugins.map((p) => [p.id, { enabled: p.enabled, ...p.config }]));
  const [pluginDraft, setPluginDraft] = useState<PluginDraft>(seedPlugins);
  const [pluginSeed, setPluginSeed] = useState<PluginDraft>(seedPlugins);
  const pluginsDirty = useMemo(
    () => JSON.stringify(pluginDraft) !== JSON.stringify(pluginSeed),
    [pluginDraft, pluginSeed],
  );

  // Preferences draft, (re)seeded each time the dialog opens.
  const seedPrefs = (): PrefsDraft => ({
    filterProfanity: props.filterProfanity, aacMode: props.aacMode, fuzzyCallsign: props.fuzzyCallsign,
    fuzzyCallsignRewrite: props.fuzzyCallsignRewrite,
    inputDevice: props.inputDevice, systemMonitorSink: props.systemMonitorSink,
    outputDevice: props.outputDevice, spectroColormap: props.spectroColormap,
    spectroFreqRange: props.spectroFreqRange, spectroTimeWindowS: props.spectroTimeWindowS,
    uiLevel: props.uiLevel, fontScale: props.fontScale, highContrast: props.highContrast,
    switchScan: props.switchScan, switchScanIntervalS: props.switchScanIntervalS, visualAlerts: props.visualAlerts,
  });
  const [draft, setDraft] = useState<PrefsDraft>(seedPrefs);
  const [prefsSeed, setPrefsSeed] = useState<PrefsDraft>(seedPrefs);

  useEffect(() => {
    if (open) {
      const s = seedPrefs();
      setDraft(s); setPrefsSeed(s); setTab(0); setAdminDirty(false); setServerDirty(false);
      const p = seedPlugins();
      setPluginDraft(p); setPluginSeed(p);
      setSaved(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const prefsDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(prefsSeed),
    [draft, prefsSeed],
  );
  const dirty = prefsDirty || (isAdmin && (adminDirty || serverDirty || pluginsDirty));

  function applyPrefs() {
    if (draft.filterProfanity !== prefsSeed.filterProfanity) props.onToggleProfanity();
    if (draft.aacMode !== prefsSeed.aacMode) props.onToggleAacMode();
    if (draft.fuzzyCallsign !== prefsSeed.fuzzyCallsign) props.onToggleFuzzy();
    if (draft.fuzzyCallsignRewrite !== prefsSeed.fuzzyCallsignRewrite) props.onToggleFuzzyRewrite();
    if (draft.inputDevice !== prefsSeed.inputDevice || draft.systemMonitorSink !== prefsSeed.systemMonitorSink)
      props.onInputDeviceChange(draft.inputDevice, draft.systemMonitorSink);
    if (draft.outputDevice !== prefsSeed.outputDevice) props.onOutputDeviceChange(draft.outputDevice);
    if (draft.spectroColormap !== prefsSeed.spectroColormap) props.onSpectroColormapChange(draft.spectroColormap);
    if (draft.spectroFreqRange !== prefsSeed.spectroFreqRange) props.onSpectroFreqRangeChange(draft.spectroFreqRange);
    if (draft.spectroTimeWindowS !== prefsSeed.spectroTimeWindowS) props.onSpectroTimeWindowChange(draft.spectroTimeWindowS);
    if (draft.uiLevel !== prefsSeed.uiLevel) props.onUiLevelChange(draft.uiLevel);
    if (draft.fontScale !== prefsSeed.fontScale) props.onFontScaleChange(draft.fontScale);
    if (draft.highContrast !== prefsSeed.highContrast) props.onToggleHighContrast();
    if (draft.switchScan !== prefsSeed.switchScan) props.onToggleSwitchScan();
    if (draft.switchScanIntervalS !== prefsSeed.switchScanIntervalS) props.onSwitchScanIntervalChange(draft.switchScanIntervalS);
    if (draft.visualAlerts !== prefsSeed.visualAlerts) props.onToggleVisualAlerts();
  }

  function handleSave() {
    if (prefsDirty) { applyPrefs(); setPrefsSeed(draft); }
    if (isAdmin && adminDirty) { adminRef.current?.save(); setAdminDirty(false); }
    if (isAdmin && serverDirty) { serverRef.current?.save(); setServerDirty(false); }
    if (isAdmin && pluginsDirty) { props.onPluginsSave(pluginDraft); setPluginSeed(pluginDraft); }
    setSaved(true);
  }

  function handleClose() {
    if (dirty) {
      setDiscardConfirmOpen(true);
      return;
    }
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
          <Tab label="Plugins" />
        </Tabs>
      )}

      <DialogContent dividers>
        <Box role="tabpanel" hidden={isAdmin && tab !== 0}>
          <ConfigPanel
            hideHeader
            filterProfanity={draft.filterProfanity}
            aacMode={draft.aacMode}
            fuzzyCallsign={draft.fuzzyCallsign}
            fuzzyCallsignRewrite={draft.fuzzyCallsignRewrite}
            inputDevice={draft.inputDevice}
            systemMonitorSink={draft.systemMonitorSink}
            inputDevices={props.inputDevices}
            monitorSinks={props.monitorSinks}
            outputDevice={draft.outputDevice}
            outputDevices={props.outputDevices}
            spectroColormap={draft.spectroColormap}
            spectroFreqRange={draft.spectroFreqRange}
            spectroTimeWindowS={draft.spectroTimeWindowS}
            uiLevel={draft.uiLevel}
            fontScale={draft.fontScale}
            highContrast={draft.highContrast}
            switchScan={draft.switchScan}
            switchScanIntervalS={draft.switchScanIntervalS}
            visualAlerts={draft.visualAlerts}
            onToggleProfanity={() => setDraft((d) => ({ ...d, filterProfanity: !d.filterProfanity }))}
            onToggleAacMode={() => setDraft((d) => ({ ...d, aacMode: !d.aacMode }))}
            onToggleFuzzy={() => setDraft((d) => ({ ...d, fuzzyCallsign: !d.fuzzyCallsign }))}
            onToggleFuzzyRewrite={() => setDraft((d) => ({ ...d, fuzzyCallsignRewrite: !d.fuzzyCallsignRewrite }))}
            onInputDeviceChange={(device, sink) => setDraft((d) => ({ ...d, inputDevice: device, systemMonitorSink: sink }))}
            onOutputDeviceChange={(device) => setDraft((d) => ({ ...d, outputDevice: device }))}
            onSpectroColormapChange={(cm) => setDraft((d) => ({ ...d, spectroColormap: cm }))}
            onSpectroFreqRangeChange={(range) => setDraft((d) => ({ ...d, spectroFreqRange: range }))}
            onSpectroTimeWindowChange={(s) => setDraft((d) => ({ ...d, spectroTimeWindowS: s }))}
            onUiLevelChange={(v) => setDraft((d) => ({ ...d, uiLevel: v }))}
            onFontScaleChange={(v) => setDraft((d) => ({ ...d, fontScale: v }))}
            onToggleHighContrast={() => setDraft((d) => ({ ...d, highContrast: !d.highContrast }))}
            onToggleSwitchScan={() => setDraft((d) => ({ ...d, switchScan: !d.switchScan }))}
            onSwitchScanIntervalChange={(v) => setDraft((d) => ({ ...d, switchScanIntervalS: v }))}
            onToggleVisualAlerts={() => setDraft((d) => ({ ...d, visualAlerts: !d.visualAlerts }))}
          />
        </Box>

        {isAdmin && (
          <Box role="tabpanel" hidden={tab !== 1}>
            <AdminPanel
              ref={adminRef} embedded hideSaveButton open={open} onClose={onClose}
              config={props.adminConfig} voices={props.voices} voicePreviewBusy={props.voicePreviewBusy}
              onSave={props.onAdminSave} onPreviewVoice={props.onPreviewVoice}
              deviceTokens={props.deviceTokens} createdToken={props.createdToken}
              onCreateDeviceToken={props.onCreateDeviceToken} onRevokeDeviceToken={props.onRevokeDeviceToken}
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
              onRescanVocabulary={props.onRescanVocabulary} onOpenCalibration={props.onOpenCalibration}
              onDirtyChange={setServerDirty}
            />
          </Box>
        )}

        {isAdmin && (
          <Box role="tabpanel" hidden={tab !== 3}>
            <PluginsPanel
              plugins={props.plugins} value={pluginDraft} onChange={setPluginDraft}
              onInstallFile={props.onInstallPlugin}
              onReload={props.onReloadPlugin}
              onUninstall={props.onUninstallPlugin}
              busy={props.pluginBusy}
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

      <ConfirmDialog
        open={discardConfirmOpen}
        title="Discard unsaved changes?"
        confirmLabel="Yes, discard"
        cancelLabel="No, keep editing"
        destructive
        onConfirm={() => { setDiscardConfirmOpen(false); onClose(); }}
        onClose={() => setDiscardConfirmOpen(false)}
      />
    </Dialog>
  );
}
