import React, { useState, useEffect, forwardRef, useImperativeHandle, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Divider,
  InputAdornment,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  ToggleButtonGroup,
  ToggleButton,
  Switch,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import MicIcon from '@mui/icons-material/Mic';
import type { VoiceOption, DeviceTokenRecord } from '../../types/ws';
import { ConfirmDialog } from '../ConfirmDialog';

const SPEED_MARKS = [
  { value: 0.5, label: 'Fast' },
  { value: 1.0, label: 'Normal' },
  { value: 1.5, label: 'Slow' },
  { value: 2.0, label: 'Slowest' },
];

const NEIGHBORHOOD_NET_DAYS = [
  'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
] as const;

interface AdminConfig {
  stationCallsign: string;
  stationName: string;
  stationLocation: string;
  stationVoice: string;
  stationLengthScale: number;
  geminiApiKeySet: boolean;
  journalsDir: string;
  ncsZone: string;
  ncsPreambleText: string;
  ncsClosingText: string;
  rxMode: string;
  /** Neighborhood net weekly schedule — full weekday name ("Sunday".."Saturday")
   *  or "" for "not scheduled". Sourced from neighborhood_state (not the
   *  status message), so callers must merge it in rather than treat it as
   *  part of the admin-config sync from `status`. */
  netDay: string;
  /** "HH:MM" 24-hour time, or "" when unset. */
  netTime: string;
  /** Quick-message shortcuts offered on the kiosk display's "I'm OK" screen. */
  display_quick_messages: string[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  config: AdminConfig;
  voices: VoiceOption[];
  voicePreviewBusy: boolean;
  onSave: (values: {
    callsign: string;
    name: string;
    location: string;
    voice: string;
    tts_length_scale: number;
    gemini_api_key: string;
    journals_dir: string;
    ncs_zone: string;
    ncs_preamble_text: string;
    ncs_closing_text: string;
    rx_mode: string;
    neighborhood_net_day: string;
    neighborhood_net_time: string;
    display_quick_messages: string[];
  }) => void;
  onPreviewVoice: (voiceId: string) => void;
  /** Wall-display device tokens, admin-managed (Task 3 device_token_* WS chain). */
  deviceTokens: DeviceTokenRecord[];
  /** The one-time token from the most recent device_token_created reply, shown
   *  once in a copyable field then never again — not persisted server-side. */
  createdToken: DeviceTokenRecord | null;
  onCreateDeviceToken: (label: string) => void;
  onRevokeDeviceToken: (id: string) => void;
  onSetDeviceTokenEink: (id: string, eink: boolean) => void;
  children?: React.ReactNode;
  /** When true, render just the form body (no Dialog chrome) for embedding in
   *  a tabbed SettingsDialog. The Save button is kept; Cancel/title are not. */
  embedded?: boolean;
  /** When true, suppress the embedded/standalone Save button (e.g. a parent
   *  dialog supplies its own footer Save button via the imperative ref). */
  hideSaveButton?: boolean;
  /** Called whenever the form's dirty state changes relative to the seed
   *  snapshot captured when the panel was last opened or imperatively saved. */
  onDirtyChange?: (dirty: boolean) => void;
}

export interface AdminPanelHandle {
  save(): void;
}

/** Build the seed JSON object from a config snapshot, mirroring buildValues(). */
function seedFromConfig(config: AdminConfig): string {
  return JSON.stringify({
    callsign: (config.stationCallsign || '').toUpperCase() || 'N0CALL',
    name: config.stationName,
    location: config.stationLocation,
    voice: config.stationVoice,
    tts_length_scale: config.stationLengthScale,
    gemini_api_key: '', // key is write-only (geminiApiKeySet)
    journals_dir: config.journalsDir,
    ncs_zone: (config.ncsZone || '').toUpperCase(),
    ncs_preamble_text: config.ncsPreambleText || '',
    ncs_closing_text: config.ncsClosingText || '',
    rx_mode: config.rxMode || 'voice',
    neighborhood_net_day: config.netDay || '',
    neighborhood_net_time: config.netTime || '',
    display_quick_messages: config.display_quick_messages || [],
  });
}

export const AdminPanel = forwardRef<AdminPanelHandle, Props>(function AdminPanel(
  { open, onClose, config, voices, voicePreviewBusy, onSave, onPreviewVoice, children,
    deviceTokens, createdToken, onCreateDeviceToken, onRevokeDeviceToken, onSetDeviceTokenEink,
    embedded = false, hideSaveButton = false, onDirtyChange },
  ref
) {
  const [callsign, setCallsign] = useState('');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [voice, setVoice] = useState('');
  const [lengthScale, setLengthScale] = useState(1.0);
  const [geminiKey, setGeminiKey] = useState('');
  const [journalsDir, setJournalsDir] = useState('');
  const [ncsZone, setNcsZone] = useState('');
  const [ncsPreambleText, setNcsPreambleText] = useState('');
  const [ncsClosingText, setNcsClosingText] = useState('');
  const [rxMode, setRxMode] = useState('voice');
  const [netDay, setNetDay] = useState('');
  const [netTime, setNetTime] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [quickMessagesText, setQuickMessagesText] = useState('');
  const [newDisplayLabel, setNewDisplayLabel] = useState('');
  const [tokenToRevoke, setTokenToRevoke] = useState<DeviceTokenRecord | null>(null);

  const seedRef = useRef<string>('');

  // Only re-initialize when the dialog opens. Keeping `config` out of the dep
  // array prevents incoming WS status messages from resetting in-progress edits.
  useEffect(() => {
    if (!open) return;
    setCallsign(config.stationCallsign);
    setName(config.stationName);
    setLocation(config.stationLocation);
    setVoice(config.stationVoice);
    setLengthScale(config.stationLengthScale);
    setGeminiKey('');
    setJournalsDir(config.journalsDir);
    setNcsZone(config.ncsZone);
    setNcsPreambleText(config.ncsPreambleText || '');
    setNcsClosingText(config.ncsClosingText || '');
    setRxMode(config.rxMode || 'voice');
    setNetDay(config.netDay || '');
    setNetTime(config.netTime || '');
    setShowKey(false);
    setQuickMessagesText((config.display_quick_messages || []).join('\n'));
    // Compute seed from config directly (state setters are async), mirroring
    // buildValues() serialization. geminiKey initializes to '' on open.
    seedRef.current = seedFromConfig(config);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // For embedded panels that start open=true (always open), seed on first mount.
  useEffect(() => {
    if (!embedded) return;
    seedRef.current = seedFromConfig(config);
    // Only run on first mount for the embedded case.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function buildValues() {
    return {
      callsign: callsign.trim().toUpperCase() || 'N0CALL',
      name: name.trim(),
      location: location.trim(),
      voice: voice.trim(),
      tts_length_scale: lengthScale,
      gemini_api_key: geminiKey.trim(),
      journals_dir: journalsDir.trim(),
      ncs_zone: ncsZone.trim().toUpperCase(),
      ncs_preamble_text: ncsPreambleText,
      ncs_closing_text: ncsClosingText,
      rx_mode: rxMode,
      neighborhood_net_day: netDay,
      neighborhood_net_time: netTime,
      display_quick_messages: quickMessagesText
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean),
    };
  }

  // Report dirty on every render (cheap; React bails out on equal state).
  useEffect(() => {
    onDirtyChange?.(JSON.stringify(buildValues()) !== seedRef.current);
  });

  function commitValues() {
    const values = buildValues();
    onSave(values);
    seedRef.current = JSON.stringify(values);
  }

  useImperativeHandle(ref, () => ({ save: commitValues }));

  function handleSave() { // used only by the embedded/standalone button
    commitValues();
    onClose();
  }

  function handleCreateDisplay() {
    const trimmed = newDisplayLabel.trim();
    if (!trimmed) return;
    onCreateDeviceToken(trimmed);
    setNewDisplayLabel('');
  }

  const content = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            Station Identity
          </Typography>

          <TextField
            label="Station Callsign"
            size="small"
            value={callsign}
            onChange={(e) => setCallsign(e.target.value.toUpperCase())}
            placeholder="N0CALL"
            slotProps={{ htmlInput: { style: { fontFamily: 'monospace', fontWeight: 700 } } }}
            fullWidth
          />

          <TextField
            label="Station Name"
            size="small"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Home Base"
            fullWidth
          />

          <TextField
            label="Station Location"
            size="small"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Grand Rapids, MI"
            fullWidth
          />

          {voices.length > 0 && (
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <FormControl size="small" sx={{ flex: 1 }}>
                <InputLabel id="admin-voice-label">Default TTS Voice</InputLabel>
                <Select
                  labelId="admin-voice-label"
                  label="Default TTS Voice"
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                >
                  {voices.map((v) => (
                    <MenuItem key={v.id} value={v.id}>{v.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <IconButton
                size="small"
                onClick={() => onPreviewVoice(voice || (voices[0]?.id ?? ''))}
                disabled={voices.length === 0 || voicePreviewBusy}
                aria-label="Preview selected voice"
                title={voicePreviewBusy ? 'Playing…' : 'Preview'}
              >
                <MicIcon fontSize="small" />
              </IconButton>
            </Box>
          )}

          <Box>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
              Default Speech Speed
            </Typography>
            <Slider
              value={lengthScale}
              min={0.5}
              max={2.0}
              step={0.25}
              marks={SPEED_MARKS}
              valueLabelDisplay="auto"
              valueLabelFormat={(v) => `${v}×`}
              onChange={(_, v) => setLengthScale(v as number)}
              aria-label="Default speech speed"
              sx={{ mt: 1 }}
            />
          </Box>

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            AI / Journals
          </Typography>

          <TextField
            label="Gemini API Key"
            size="small"
            type={showKey ? 'text' : 'password'}
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
            placeholder={config.geminiApiKeySet ? 'API key configured — enter new to replace' : 'Paste API key here'}
            fullWidth
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      size="small"
                      onClick={() => setShowKey((v) => !v)}
                      aria-label={showKey ? 'Hide API key' : 'Show API key'}
                      edge="end"
                    >
                      {showKey ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
                    </IconButton>
                  </InputAdornment>
                ),
              },
            }}
          />

          <TextField
            label="Journals Directory"
            size="small"
            value={journalsDir}
            onChange={(e) => setJournalsDir(e.target.value)}
            placeholder="/data/journals"
            slotProps={{ htmlInput: { style: { fontFamily: 'monospace', fontSize: '0.85rem' } } }}
            fullWidth
          />

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            NCS / SKYWARN
          </Typography>

          <TextField
            label="NWS County Zone"
            size="small"
            value={ncsZone}
            onChange={(e) => setNcsZone(e.target.value.toUpperCase())}
            placeholder="e.g. MIZ025"
            helperText="NWS county zone code for SKYWARN alerts. Leave blank to disable."
            slotProps={{ htmlInput: { style: { fontFamily: 'monospace', fontWeight: 700 } } }}
            fullWidth
          />

          <TextField
            label="Net Opening Preamble"
            size="small"
            value={ncsPreambleText}
            onChange={(e) => setNcsPreambleText(e.target.value)}
            placeholder="This is the weekly net. All stations welcome…"
            helperText="Read on the air via the NCS panel. Placeholders: {callsign} {name} {location} {date} {time}"
            multiline
            minRows={2}
            fullWidth
          />

          <TextField
            label="Net Closing Script"
            size="small"
            value={ncsClosingText}
            onChange={(e) => setNcsClosingText(e.target.value)}
            placeholder="Thanks to all who checked in. This net is now closed…"
            helperText="Read on the air via the NCS panel. Same placeholders as the preamble."
            multiline
            minRows={2}
            fullWidth
          />

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            Neighborhood
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel id="neighborhood-net-day-label">Net Day</InputLabel>
              <Select
                labelId="neighborhood-net-day-label"
                label="Net Day"
                value={netDay}
                displayEmpty
                onChange={(e) => setNetDay(e.target.value)}
              >
                <MenuItem value="">Not scheduled</MenuItem>
                {NEIGHBORHOOD_NET_DAYS.map((day) => (
                  <MenuItem key={day} value={day}>{day}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              label="Net Time"
              type="time"
              size="small"
              value={netTime}
              onChange={(e) => setNetTime(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Box>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Weekly neighborhood net schedule, shown on the Neighborhood activity and home card.
          </Typography>

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            Receive Mode
          </Typography>

          <Box>
            <ToggleButtonGroup
              size="small"
              exclusive
              value={rxMode}
              onChange={(_, v) => v && setRxMode(v)}
              aria-label="Receive mode"
            >
              <ToggleButton value="voice">Voice (STT)</ToggleButton>
              <ToggleButton value="cw">CW / Morse</ToggleButton>
            </ToggleButtonGroup>
            <Typography variant="caption" sx={{ display: 'block', mt: 0.75, color: 'text.secondary' }}>
              {rxMode === 'cw'
                ? 'Incoming audio decoded as morse code. Whisper STT is disabled.'
                : 'Incoming audio transcribed with Whisper speech-to-text.'}
            </Typography>
          </Box>

          <Divider />

          <Typography variant="overline" sx={{ color: 'text.secondary', lineHeight: 1 }}>
            Wall displays
          </Typography>

          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Display</TableCell>
                <TableCell>Created</TableCell>
                <TableCell>Last Seen</TableCell>
                <TableCell align="center">E-ink</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {deviceTokens.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>{t.label}</TableCell>
                  <TableCell>{t.created_at}</TableCell>
                  <TableCell>{t.last_seen ?? 'Never'}</TableCell>
                  <TableCell align="center">
                    <Switch
                      size="small"
                      checked={t.eink ?? false}
                      onChange={(e) => onSetDeviceTokenEink(t.id, e.target.checked)}
                      slotProps={{ input: { 'aria-label': `E-ink mode for ${t.label}` } }}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      size="small"
                      color="error"
                      aria-label={`Revoke ${t.label}`}
                      onClick={() => setTokenToRevoke(t)}
                    >
                      Revoke
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {deviceTokens.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                      No wall displays yet.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              size="small"
              fullWidth
              label="Display Name"
              value={newDisplayLabel}
              onChange={(e) => setNewDisplayLabel(e.target.value)}
              placeholder="e.g. Kitchen"
            />
            <Button
              variant="outlined"
              onClick={handleCreateDisplay}
              disabled={!newDisplayLabel.trim()}
            >
              Add display
            </Button>
          </Box>

          {createdToken && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              <TextField
                size="small"
                fullWidth
                label={`Token for ${createdToken.label}`}
                value={createdToken.token ?? ''}
                slotProps={{ htmlInput: { readOnly: true, style: { fontFamily: 'monospace' } } }}
              />
              <Typography variant="caption" color="warning.main">
                Copy now — it won't be shown again.
              </Typography>
            </Box>
          )}

          <TextField
            label="Household Quick Messages"
            size="small"
            value={quickMessagesText}
            onChange={(e) => setQuickMessagesText(e.target.value)}
            multiline
            minRows={3}
            fullWidth
            helperText="Buttons shown on the wall display. One message per line."
          />

          {children && (
            <>
              <Divider />
              {children}
            </>
          )}

        </Box>
  );

  const saveButton = hideSaveButton ? null : (
    <Button onClick={handleSave} variant="contained">Save</Button>
  );

  const revokeConfirmDialog = (
    <ConfirmDialog
      open={tokenToRevoke !== null}
      title="Revoke this display?"
      body={tokenToRevoke ? `"${tokenToRevoke.label}" will stop working immediately.` : ''}
      confirmLabel="Yes, revoke it"
      destructive
      onConfirm={() => { if (tokenToRevoke) onRevokeDeviceToken(tokenToRevoke.id); }}
      onClose={() => setTokenToRevoke(null)}
    />
  );

  if (embedded) {
    return (
      <Box sx={{ pt: 1 }}>
        {content}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
          {saveButton}
        </Box>
        {revokeConfirmDialog}
      </Box>
    );
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Admin Settings</DialogTitle>
        <DialogContent dividers>{content}</DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={onClose} variant="outlined">Cancel</Button>
          {saveButton}
        </DialogActions>
      </Dialog>
      {revokeConfirmDialog}
    </>
  );
});
