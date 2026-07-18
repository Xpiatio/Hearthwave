import { useEffect, useState } from 'react';
import { Alert, Box, Button, Chip, Paper, TextField, Typography } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import { useDisplaySocket } from '../../hooks/useDisplaySocket';
import type { UseDisplaySocketResult } from '../../hooks/useDisplaySocket';
import { isDuskDark } from '../../display/autoDark';
import { makeTheme } from '../../theme';
import { nextNetLabel } from '../../neighborhood/schedule';
import { PresenceTile } from './PresenceTile';

const DEVICE_TOKEN_KEY = 'radio_tty_device_token';

const CLOCK_TICK_MS = 30_000;
const DRIFT_TICK_MS = 60_000;

// Burn-in mitigation: cycle the whole layout through 9 small offsets so no
// pixel sits under the same content for hours on end.
const DRIFT_OFFSETS: Array<{ x: number; y: number }> = [
  { x: -8, y: -8 }, { x: -8, y: 0 }, { x: -8, y: 8 },
  { x: 0, y: -8 }, { x: 0, y: 0 }, { x: 0, y: 8 },
  { x: 8, y: -8 }, { x: 8, y: 0 }, { x: 8, y: 8 },
];

function formatClock(d: Date): string {
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

function formatDate(d: Date): string {
  return d.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
}

export function DisplayApp() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(DEVICE_TOKEN_KEY));
  const [tokenInput, setTokenInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Single socket for the component's lifetime — the connected layout below
  // consumes the same result rather than opening a second connection.
  const socket = useDisplaySocket(token);
  const { authFailed } = socket;

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

  return <ConnectedDisplay socket={socket} />;
}

function ConnectedDisplay({ socket }: { socket: UseDisplaySocketResult }) {
  const { connected, presence, neighborhood, messages, alert } = socket;
  const [now, setNow] = useState(() => new Date());
  const [driftIndex, setDriftIndex] = useState(0);

  // Clock ticks every 30s; theme (auto-dark) is re-evaluated on the same
  // tick since it only needs hour-granularity, not a live second-hand.
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), CLOCK_TICK_MS);
    return () => clearInterval(id);
  }, []);

  // Burn-in drift: nudge the whole layout through 9 small offsets every
  // 60s so static content doesn't scorch the same pixels for hours.
  useEffect(() => {
    const id = setInterval(() => {
      setDriftIndex((i) => (i + 1) % DRIFT_OFFSETS.length);
    }, DRIFT_TICK_MS);
    return () => clearInterval(id);
  }, []);

  const theme = makeTheme(isDuskDark(now), { fontScale: 1.25 });
  const drift = DRIFT_OFFSETS[driftIndex];

  return (
    <ThemeProvider theme={theme}>
      <Box
        data-testid="display-shell"
        sx={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          p: 3,
          gap: 2,
          bgcolor: 'background.default',
          color: 'text.primary',
          transform: `translate(${drift.x}px, ${drift.y}px)`,
        }}
      >
        <Box component="header" sx={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
          <Typography sx={{ fontSize: '4rem', fontWeight: 700 }}>{formatClock(now)}</Typography>
          <Typography sx={{ fontSize: '1.5rem', color: 'text.secondary' }}>{formatDate(now)}</Typography>
          {!connected && <Chip color="error" label="Reconnecting…" />}
        </Box>

        {alert && (
          <Alert
            severity={alert.kind === 'weather' ? 'warning' : 'error'}
            role="alert"
            sx={{ fontSize: '1.4rem' }}
          >
            {alert.message}
          </Alert>
        )}

        <Box
          role="list"
          aria-label="Family"
          sx={{
            display: 'grid',
            gap: 2,
            flexGrow: 1,
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            alignContent: 'start',
          }}
        >
          {presence.map((e) => (
            <Box role="listitem" key={e.user_id}>
              <PresenceTile entry={e} now={now} interactive={false} />
            </Box>
          ))}
        </Box>

        <Box component="footer" sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
          <Box role="group" aria-label="Recent messages">
            {messages.slice(-3).map((m) => (
              <Typography key={m.id} noWrap sx={{ fontSize: '1.1rem' }}>
                {m.sender && <b>{m.sender} </b>}
                {m.text}
              </Typography>
            ))}
          </Box>
          <Typography sx={{ fontSize: '1.2rem', color: 'text.secondary' }}>
            {neighborhood?.active
              ? 'Net running now'
              : neighborhood
                ? nextNetLabel(neighborhood.net_day, neighborhood.net_time, now)
                : ''}
          </Typography>
        </Box>
      </Box>
    </ThemeProvider>
  );
}
