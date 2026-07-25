import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Box, Button, Chip, Link, Paper, Snackbar, TextField, Typography } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';
import { useDisplaySocket } from '../../hooks/useDisplaySocket';
import type { UseDisplaySocketResult } from '../../hooks/useDisplaySocket';
import { isDuskDark } from '../../display/autoDark';
import { makeTheme } from '../../theme';
import { nextNetLabel } from '../../neighborhood/schedule';
import { tileMetrics } from '../../display/tileSize';
import { applyTileOrder, reorderIds } from '../../display/tileOrder';
import { PresenceTile } from './PresenceTile';
import { SortablePresenceTile } from './SortablePresenceTile';
import { ConfirmOkDialog } from './ConfirmOkDialog';
import { DisplayChatConsole } from './DisplayChatConsole';
import type { DisplayImOkPayload, DisplayQuickMessagePayload, FamilyPresenceEntry } from '../../types/ws';

const DEVICE_TOKEN_KEY = 'radio_tty_device_token';

// A long-press, not a tap: short taps still belong to "Mark OK".
const DRAG_DELAY_MS = 350;
const DRAG_TOLERANCE_PX = 8;

const CLOCK_TICK_MS = 30_000;
const DRIFT_TICK_MS = 60_000;
// Tap-to-wake: how long the kiosk stays in interactive mode after a tap
// before reverting to the passive wall-display layout.
const WAKE_WINDOW_MS = 45_000;

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

/** Read the pairing token from `?token=`, then scrub it from the address bar.
 *
 *  A bookmarked `/display?token=…` is the kiosk's belt-and-braces pairing: it
 *  survives a browser that clears site data between sessions, which plain
 *  localStorage does not. The trade-off is that the token lands in bookmarks
 *  and history, so it is stripped from the visible URL immediately.
 */
function takeTokenFromUrl(): string | null {
  try {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = (params.get('token') || '').trim();
    if (!fromUrl) return null;
    params.delete('token');
    const query = params.toString();
    window.history.replaceState(
      null,
      '',
      `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`,
    );
    return fromUrl;
  } catch {
    return null;
  }
}

export function DisplayApp() {
  const [token, setToken] = useState<string | null>(() => {
    const fromUrl = takeTokenFromUrl();
    if (fromUrl) {
      localStorage.setItem(DEVICE_TOKEN_KEY, fromUrl);
      return fromUrl;
    }
    return localStorage.getItem(DEVICE_TOKEN_KEY);
  });
  const [codeInput, setCodeInput] = useState('');
  const [tokenInput, setTokenInput] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [pairing, setPairing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Single socket for the component's lifetime — the connected layout below
  // consumes the same result rather than opening a second connection.
  const socket = useDisplaySocket(token);
  const { authFailed } = socket;

  // Auth failure no longer wipes the pairing on its own. The hook only raises
  // this for an explicit "device_token_invalid", and even then the operator
  // decides — a kiosk that un-pairs itself is how this display ended up
  // asking for a token on every visit.
  function handleRepair() {
    localStorage.removeItem(DEVICE_TOKEN_KEY);
    setToken(null);
    setCodeInput('');
    setTokenInput('');
    setError('This display was unpaired. Ask an admin for a new pairing code.');
  }

  function storeToken(value: string) {
    localStorage.setItem(DEVICE_TOKEN_KEY, value);
    setError(null);
    setToken(value);
  }

  function handleConnect() {
    const trimmed = tokenInput.trim();
    if (!trimmed) return;
    storeToken(trimmed);
  }

  async function handlePair() {
    const code = codeInput.trim();
    if (!code || pairing) return;
    setPairing(true);
    setError(null);
    try {
      const res = await fetch('/display/pair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(detail?.detail || 'That code is not valid. Ask for a new one.');
        return;
      }
      const data = (await res.json()) as { token?: string };
      if (!data.token) {
        setError('The server did not return a token. Ask an admin to try again.');
        return;
      }
      storeToken(data.token);
    } catch {
      setError('Could not reach the radio. Check the connection and try again.');
    } finally {
      setPairing(false);
    }
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
            Enter the pairing code from Settings → Station → Wall displays
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <TextField
            label="Pairing code"
            value={codeInput}
            onChange={(e) => setCodeInput(e.target.value.replace(/\D/g, '').slice(0, 6))}
            onKeyDown={(e) => { if (e.key === 'Enter') void handlePair(); }}
            fullWidth
            autoFocus
            slotProps={{
              htmlInput: {
                inputMode: 'numeric',
                autoComplete: 'one-time-code',
                autoCapitalize: 'off',
                autoCorrect: 'off',
                spellCheck: false,
                style: { fontSize: '2rem', letterSpacing: '0.4em', textAlign: 'center' },
              },
              inputLabel: { shrink: true },
            }}
            sx={{ mb: 2 }}
          />

          <Button
            variant="contained"
            fullWidth
            size="large"
            disabled={codeInput.trim().length < 6 || pairing}
            onClick={() => void handlePair()}
          >
            {pairing ? 'Pairing…' : 'Pair this display'}
          </Button>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Link
              component="button"
              type="button"
              underline="hover"
              variant="body2"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? 'Hide' : 'Paste a device token instead'}
            </Link>
          </Box>

          {showAdvanced && (
            <Box sx={{ mt: 2 }}>
              <TextField
                label="Device token"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleConnect(); }}
                fullWidth
                slotProps={{
                  htmlInput: { autoCapitalize: 'off', autoCorrect: 'off', spellCheck: false },
                  inputLabel: { shrink: true },
                }}
                sx={{ mb: 2 }}
              />
              <Button
                variant="outlined"
                fullWidth
                size="large"
                disabled={!tokenInput.trim()}
                onClick={handleConnect}
              >
                Connect
              </Button>
            </Box>
          )}
        </Paper>
      </Box>
    );
  }

  return <ConnectedDisplay socket={socket} unpaired={authFailed} onRepair={handleRepair} />;
}

function ConnectedDisplay({
  socket,
  unpaired,
  onRepair,
}: {
  socket: UseDisplaySocketResult;
  unpaired: boolean;
  onRepair: () => void;
}) {
  const { connected, presence, neighborhood, messages, alert, status, lastAck, eink, order, send } = socket;
  const [now, setNow] = useState(() => new Date());
  const [driftIndex, setDriftIndex] = useState(0);

  // Tap-to-wake: awakeUntil is the epoch ms the interactive window expires.
  // 0 means passive/asleep. nowMs only ticks (once a second) while awake, so
  // the wall display isn't re-rendering every second forever.
  const [awakeUntil, setAwakeUntil] = useState(0);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [confirmEntry, setConfirmEntry] = useState<FamilyPresenceEntry | null>(null);
  const [sentSnackOpen, setSentSnackOpen] = useState(false);

  // Local order wins after a drag; the server's copy is the fallback and the
  // source of truth on a fresh connect.
  const [localOrder, setLocalOrder] = useState<string[] | null>(null);
  const serverOrderRef = useRef<string[]>(order);
  useEffect(() => {
    // A reconnect re-delivers display_config; adopt it and drop the local
    // copy so a revoked-then-restored panel doesn't keep a stale order.
    if (serverOrderRef.current !== order) {
      serverOrderRef.current = order;
      setLocalOrder(null);
    }
  }, [order]);

  const interactive = awakeUntil > nowMs;

  const orderedPresence = useMemo(
    () => applyTileOrder(presence, localOrder ?? order),
    [presence, localOrder, order],
  );
  const metrics = tileMetrics(orderedPresence.length);

  // Long-press to drag so a short tap still means "Mark OK"; keyboard sorting
  // comes along for free, which matters for the switch-scanning work.
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { delay: DRAG_DELAY_MS, tolerance: DRAG_TOLERANCE_PX },
    }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  // E-ink smears on movement — no drag animation on those panels.
  const sortable = interactive && !eink;

  // The people board fills what's left of the right-hand column under the
  // clock: tiles shrink to a floor, then the board scrolls.
  const peopleBoardSx = {
    display: 'grid',
    gap: 2,
    flexGrow: 1,
    minHeight: 0,
    overflowY: 'auto',
    gridTemplateColumns: `repeat(auto-fit, minmax(${metrics.minWidth}px, 1fr))`,
    alignContent: 'start',
  } as const;

  function wake() {
    setAwakeUntil(Date.now() + WAKE_WINDOW_MS);
  }

  // Only tick while a wake window is active; the tick itself is what
  // notices expiry and clears awakeUntil, which stops the interval again.
  useEffect(() => {
    if (awakeUntil <= 0) return undefined;
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [awakeUntil]);

  useEffect(() => {
    if (awakeUntil > 0 && nowMs >= awakeUntil) {
      setAwakeUntil(0);
    }
  }, [nowMs, awakeUntil]);

  // Quick-message "Sent" snackbar is driven entirely by the server ack, not
  // by the local send — the kiosk shouldn't claim success before the
  // backend actually accepted it.
  useEffect(() => {
    if (lastAck?.action === 'quick_message') {
      setSentSnackOpen(true);
    }
  }, [lastAck]);

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

  function handleImOk(entry: FamilyPresenceEntry) {
    setConfirmEntry(entry);
  }

  function handleConfirmOk(entry: FamilyPresenceEntry) {
    const payload: DisplayImOkPayload = { type: 'display_im_ok', user_id: entry.user_id };
    send(payload);
  }

  function handleQuickMessage(text: string) {
    const payload: DisplayQuickMessagePayload = { type: 'display_quick_message', text };
    send(payload);
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over) return;
    const current = orderedPresence.map((e) => e.user_id);
    const next = reorderIds(current, String(active.id), String(over.id));
    if (next === current) return;
    // Optimistic: the wall reflects the drag immediately, and the server
    // echoes nothing back for order — the device token is the record.
    setLocalOrder(next);
    send({ type: 'display_set_order', order: next });
  }

  const theme = makeTheme(eink ? false : isDuskDark(now), { fontScale: 1.25, eink });
  // E-ink has no OLED-style burn-in and smears on movement — pin at origin.
  const drift = eink ? { x: 0, y: 0 } : DRIFT_OFFSETS[driftIndex];
  const quickMessages = status?.display_quick_messages ?? [];
  const netLabel = neighborhood?.active
    ? 'Net running now'
    : neighborhood
      ? nextNetLabel(neighborhood.net_day, neighborhood.net_time, now)
      : '';

  return (
    <ThemeProvider theme={theme}>
      <Box
        data-testid="display-shell"
        onClick={wake}
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
        <Box
          sx={{
            display: 'grid',
            gap: 2,
            flexGrow: 1,
            minHeight: 0,
            // The right column carries the people board as well as the clock,
            // so it needs room for two tiles side by side at the largest tier.
            gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1.4fr) minmax(320px, 1fr)' },
          }}
        >
          <DisplayChatConsole messages={messages} eink={eink} />

          <Box
            component="header"
            sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, minWidth: 0, minHeight: 0 }}
          >
            <Typography sx={{ fontSize: '4rem', fontWeight: 700, lineHeight: 1 }}>
              {formatClock(now)}
            </Typography>
            <Typography sx={{ fontSize: '1.5rem', color: 'text.secondary' }}>
              {formatDate(now)}
            </Typography>
            {!connected && <Chip color="error" label="Reconnecting…" sx={{ alignSelf: 'flex-start' }} />}

            {unpaired && (
              <Alert
                severity="error"
                role="alert"
                action={<Button color="inherit" size="small" onClick={onRepair}>Re-pair</Button>}
              >
                This display is no longer paired. Ask an admin for a new pairing code.
              </Alert>
            )}

            {alert && (
              <Alert
                severity={alert.kind === 'weather' ? 'warning' : 'error'}
                role="alert"
                sx={{ fontSize: '1.4rem' }}
              >
                {alert.message}
              </Alert>
            )}

            {netLabel && (
              <Typography sx={{ fontSize: '1.25rem', color: eink ? 'text.primary' : 'warning.main' }}>
                {netLabel}
              </Typography>
            )}

            {/* The DndContext must sit OUTSIDE role="list" — it renders its
                own screen-reader live region, which is not a permitted list
                child. */}
            {sortable ? (
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                <Box role="list" aria-label="Family" sx={peopleBoardSx}>
                  <SortableContext
                    items={orderedPresence.map((e) => e.user_id)}
                    strategy={rectSortingStrategy}
                  >
                    {orderedPresence.map((e) => (
                      <SortablePresenceTile
                        key={e.user_id}
                        entry={e}
                        now={now}
                        interactive
                        onImOk={handleImOk}
                        metrics={metrics}
                      />
                    ))}
                  </SortableContext>
                </Box>
              </DndContext>
            ) : (
              <Box role="list" aria-label="Family" sx={peopleBoardSx}>
                {orderedPresence.map((e) => (
                  <Box role="listitem" key={e.user_id}>
                    <PresenceTile
                      entry={e}
                      now={now}
                      interactive={interactive}
                      onImOk={handleImOk}
                      metrics={metrics}
                    />
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        </Box>

        {interactive && quickMessages.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            {quickMessages.map((text) => (
              <Button
                key={text}
                variant="contained"
                onClick={() => handleQuickMessage(text)}
                sx={{ minHeight: 72, fontSize: '1.3rem' }}
              >
                {text}
              </Button>
            ))}
          </Box>
        )}

        <ConfirmOkDialog
          entry={confirmEntry}
          onConfirm={handleConfirmOk}
          onClose={() => setConfirmEntry(null)}
        />

        <Snackbar
          open={sentSnackOpen}
          autoHideDuration={3000}
          onClose={() => setSentSnackOpen(false)}
          message="Sent"
        />
      </Box>
    </ThemeProvider>
  );
}
