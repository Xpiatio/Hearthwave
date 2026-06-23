import { useRef } from 'react';
import {
  Box, Typography, Switch, FormControlLabel, Chip, Paper, Alert, Button, Divider,
} from '@mui/material';
import type { PluginManifest } from '../../types/ws';
import { PluginConfigForm } from './PluginConfigForm';

/** Per-plugin draft: { enabled, ...configFieldValues }, keyed by plugin id. */
export type PluginDraft = Record<string, Record<string, unknown>>;

interface Props {
  plugins: PluginManifest[];
  value: PluginDraft;
  onChange: (next: PluginDraft) => void;
  /** Install a plugin from an uploaded .zip (immediate, not part of Save). */
  onInstallFile?: (file: File) => void;
  /** Reload a plugin from disk (picks up edits / re-runs setup). */
  onReload?: (id: string) => void;
  /** Uninstall a plugin (unload + remove its files). */
  onUninstall?: (id: string) => void;
  /** True while an install/reload/uninstall request is in flight. */
  busy?: boolean;
}

/**
 * Plugins manager — the "installed packages" view. Lists every installed plugin
 * with an enable/disable toggle, its declarative settings form, conflicts, and
 * any load error. Admins can install a plugin from a .zip, reload it, or remove
 * it. Enabling a plugin auto-disables the plugins it conflicts with (mirrors the
 * server-side guarantee), so two conflicting plugins can never be enabled at once.
 */
export function PluginsPanel({ plugins, value, onChange, onInstallFile, onReload, onUninstall, busy }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const nameById = Object.fromEntries(plugins.map((p) => [p.id, p.name]));

  function draftFor(p: PluginManifest): Record<string, unknown> {
    return value[p.id] ?? { enabled: p.enabled, ...p.config };
  }

  function handleToggle(plugin: PluginManifest, checked: boolean) {
    const next: PluginDraft = { ...value, [plugin.id]: { ...draftFor(plugin), enabled: checked } };
    if (checked) {
      for (const peerId of plugin.conflicts_with) {
        const peer = plugins.find((p) => p.id === peerId);
        if (peer) next[peerId] = { ...(next[peerId] ?? draftFor(peer)), enabled: false };
      }
    }
    onChange(next);
  }

  function handleField(plugin: PluginManifest, key: string, val: unknown) {
    onChange({ ...value, [plugin.id]: { ...draftFor(plugin), [key]: val } });
  }

  function handlePick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file && onInstallFile) onInstallFile(file);
    e.target.value = ''; // allow re-selecting the same file
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
      <Alert severity="warning" variant="outlined" sx={{ py: 0.5 }}>
        Plugins run with full server access. Only install plugins you trust.
      </Alert>

      {onInstallFile && (
        <Box>
          <input ref={fileRef} type="file" accept=".zip" hidden onChange={handlePick} />
          <Button variant="outlined" size="small" disabled={busy} onClick={() => fileRef.current?.click()}>
            Install plugin (.zip)…
          </Button>
        </Box>
      )}

      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        Enable or disable installed plugins. Disabling a plugin hides its UI and stops its functionality.
      </Typography>

      {plugins.length === 0 && (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>No plugins installed.</Typography>
      )}

      {plugins.map((plugin) => {
        const draft = draftFor(plugin);
        const enabled = Boolean(draft.enabled);
        const conflictNames = plugin.conflicts_with.map((id) => nameById[id]).filter(Boolean);
        return (
          <Paper key={plugin.id} variant="outlined" sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{plugin.name}</Typography>
                {plugin.version && <Chip label={`v${plugin.version}`} size="small" variant="outlined" />}
              </Box>
              {!plugin.error && (
                <FormControlLabel
                  sx={{ m: 0 }}
                  control={
                    <Switch checked={enabled} size="small"
                            onChange={(e) => handleToggle(plugin, e.target.checked)} />
                  }
                  label={enabled ? 'Enabled' : 'Disabled'}
                  labelPlacement="start"
                />
              )}
            </Box>

            {plugin.description && (
              <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
                {plugin.description}
              </Typography>
            )}

            {plugin.error && (
              <Alert severity="error" variant="outlined" sx={{ mt: 1, py: 0.5 }}>
                Failed to load: {plugin.error}
              </Alert>
            )}

            {conflictNames.length > 0 && (
              <Typography variant="caption" sx={{ color: 'warning.main', display: 'block', mt: 1 }}>
                Enabling this disables: {conflictNames.join(', ')}
              </Typography>
            )}

            {enabled && !plugin.error && (
              <PluginConfigForm
                schema={plugin.config_schema}
                values={draft}
                onChange={(key, val) => handleField(plugin, key, val)}
              />
            )}

            {(onReload || onUninstall) && (
              <>
                <Divider sx={{ mt: 2 }} />
                <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
                  {onReload && (
                    <Button size="small" disabled={busy} onClick={() => onReload(plugin.id)}>Reload</Button>
                  )}
                  {onUninstall && (
                    <Button size="small" color="error" disabled={busy}
                            onClick={() => onUninstall(plugin.id)}>Uninstall</Button>
                  )}
                </Box>
              </>
            )}
          </Paper>
        );
      })}
    </Box>
  );
}
