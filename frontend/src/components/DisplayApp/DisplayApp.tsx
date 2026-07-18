import { useEffect, useState } from 'react';
import { Alert, Box, Button, Paper, TextField, Typography } from '@mui/material';
import { useDisplaySocket } from '../../hooks/useDisplaySocket';

const DEVICE_TOKEN_KEY = 'radio_tty_device_token';

export function DisplayApp() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(DEVICE_TOKEN_KEY));
  const [tokenInput, setTokenInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  const { connected, authFailed } = useDisplaySocket(token);

  // Auth failure: the stored token is no longer valid (revoked/bad) — drop
  // it and fall back to the entry screen with an explanatory error.
  useEffect(() => {
    if (authFailed) {
      localStorage.removeItem(DEVICE_TOKEN_KEY);
      setToken(null);
      setError('That device token was not accepted. Ask an admin for a new one.');
    }
  }, [authFailed]);

  function handleConnect() {
    const trimmed = tokenInput.trim();
    if (!trimmed) return;
    localStorage.setItem(DEVICE_TOKEN_KEY, trimmed);
    setError(null);
    setToken(trimmed);
  }

  if (!token) {
    return (
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'background.default',
          p: 2,
        }}
      >
        <Paper elevation={4} sx={{ width: '100%', maxWidth: 420, p: 4 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5, textAlign: 'center' }}>
            Hearthwave Display
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center', mb: 3 }}>
            Enter this device's token to connect
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <TextField
            label="Device token"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleConnect(); }}
            fullWidth
            autoFocus
            slotProps={{
              htmlInput: { autoCapitalize: 'off', autoCorrect: 'off', spellCheck: false },
              inputLabel: { shrink: true },
            }}
            sx={{ mb: 2 }}
          />

          <Button
            variant="contained"
            fullWidth
            size="large"
            disabled={!tokenInput.trim()}
            onClick={handleConnect}
          >
            Connect
          </Button>
        </Paper>
      </Box>
    );
  }

  // Connected placeholder shell — full kiosk layout lands in a later task.
  return (
    <Box
      data-testid="display-shell"
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
      }}
    >
      <Typography variant="h6" sx={{ color: 'text.secondary' }}>
        {connected ? 'Connected' : 'Connecting…'}
      </Typography>
    </Box>
  );
}
