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
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';

interface AdminConfig {
  stationCallsign: string;
  stationName: string;
  stationLocation: string;
  geminiApiKeySet: boolean;
  journalsDir: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  config: AdminConfig;
  onSave: (values: {
    callsign: string;
    name: string;
    location: string;
    gemini_api_key: string;
    journals_dir: string;
  }) => void;
  children?: React.ReactNode;
}

export function AdminPanel({ open, onClose, config, onSave, children }: Props) {
  const [callsign, setCallsign] = useState('');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [journalsDir, setJournalsDir] = useState('');
  const [showKey, setShowKey] = useState(false);

  // Only re-initialize when the dialog opens. Keeping `config` out of the dep
  // array prevents incoming WS status messages from resetting in-progress edits.
  useEffect(() => {
    if (!open) return;
    setCallsign(config.stationCallsign);
    setName(config.stationName);
    setLocation(config.stationLocation);
    setGeminiKey('');
    setJournalsDir(config.journalsDir);
    setShowKey(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleSave() {
    onSave({
      callsign: callsign.trim().toUpperCase() || 'N0CALL',
      name: name.trim(),
      location: location.trim(),
      gemini_api_key: geminiKey.trim(),
      journals_dir: journalsDir.trim(),
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
