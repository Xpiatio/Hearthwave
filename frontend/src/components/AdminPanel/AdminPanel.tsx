import React, { useState, useEffect } from 'react';
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
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import MicIcon from '@mui/icons-material/Mic';
import type { VoiceOption } from '../../types/ws';

const SPEED_MARKS = [
  { value: 0.5, label: 'Fast' },
  { value: 1.0, label: 'Normal' },
  { value: 1.5, label: 'Slow' },
  { value: 2.0, label: 'Slowest' },
];

interface AdminConfig {
  stationCallsign: string;
  stationName: string;
  stationLocation: string;
  stationVoice: string;
  stationLengthScale: number;
  geminiApiKeySet: boolean;
  journalsDir: string;
  ncsZone: string;
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
  }) => void;
  onPreviewVoice: (voiceId: string) => void;
  children?: React.ReactNode;
}

export function AdminPanel({ open, onClose, config, voices, voicePreviewBusy, onSave, onPreviewVoice, children }: Props) {
  const [callsign, setCallsign] = useState('');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [voice, setVoice] = useState('');
  const [lengthScale, setLengthScale] = useState(1.0);
  const [geminiKey, setGeminiKey] = useState('');
  const [journalsDir, setJournalsDir] = useState('');
  const [ncsZone, setNcsZone] = useState('');
  const [showKey, setShowKey] = useState(false);

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
    setShowKey(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleSave() {
    onSave({
      callsign: callsign.trim().toUpperCase() || 'N0CALL',
      name: name.trim(),
      location: location.trim(),
      voice: voice.trim(),
      tts_length_scale: lengthScale,
      gemini_api_key: geminiKey.trim(),
      journals_dir: journalsDir.trim(),
      ncs_zone: ncsZone.trim().toUpperCase(),
    });
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>Admin Settings</DialogTitle>

      <DialogContent dividers>
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

          {children && (
            <>
              <Divider />
              {children}
            </>
          )}

        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} variant="outlined">Cancel</Button>
        <Button onClick={handleSave} variant="contained">Save</Button>
      </DialogActions>
    </Dialog>
  );
}
