import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Divider,
} from '@mui/material';
import type { AuthError, SetupData } from '../../hooks/useAuth';

interface Props {
  onSetup: (data: SetupData) => Promise<unknown>;
}

export function SetupScreen({ onSetup }: Props) {
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [operatorName, setOperatorName] = useState('');
  const [callsign, setCallsign] = useState('');
  const [location, setLocation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const passwordMismatch = confirm.length > 0 && password !== confirm;
  const canSubmit =
    displayName.trim().length > 0 &&
    password.length >= 8 &&
    password === confirm &&
    !loading;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      await onSetup({
        display_name: displayName.trim(),
        password,
        operator_name: operatorName.trim() || undefined,
        callsign: callsign.trim() || undefined,
        location: location.trim() || undefined,
      });
    } catch (err: unknown) {
      const detail = (err as Partial<AuthError>)?.detail ?? 'Setup failed. Please try again.';
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

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
      <Card sx={{ width: '100%', maxWidth: 460 }} elevation={4}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5, textAlign: 'center' }}>
            Radio-TTY
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center', mb: 3 }}>
            Create your admin account to get started
          </Typography>

          <Box component="form" onSubmit={handleSubmit} noValidate>
            <TextField
              label="Display Name"
              value={displayName}
              onChange={(e) => { setDisplayName(e.target.value); setError(null); }}
              fullWidth
              required
              autoFocus
              autoComplete="username"
              sx={{ mb: 2 }}
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(null); }}
              fullWidth
              required
              autoComplete="new-password"
              helperText="Minimum 8 characters"
              sx={{ mb: 2 }}
            />
            <TextField
              label="Confirm Password"
              type="password"
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setError(null); }}
              fullWidth
              required
              autoComplete="new-password"
              error={passwordMismatch}
              helperText={passwordMismatch ? "Passwords don't match" : ' '}
              sx={{ mb: 2 }}
            />

            <Divider sx={{ my: 1 }} />
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1.5 }}>
              Station info (optional — can be changed later)
            </Typography>

            <TextField
              label="Operator Name"
              value={operatorName}
              onChange={(e) => setOperatorName(e.target.value)}
              fullWidth
              helperText="Name used in radio transmissions"
              sx={{ mb: 2 }}
            />
            <TextField
              label="Call Sign"
              value={callsign}
              onChange={(e) => setCallsign(e.target.value.toUpperCase())}
              fullWidth
              slotProps={{ input: { style: { fontFamily: 'monospace' } } }}
              sx={{ mb: 2 }}
            />
            <TextField
              label="Location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              fullWidth
              sx={{ mb: 2 }}
            />

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={!canSubmit}
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
            >
              {loading ? 'Creating account…' : 'Create Account'}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
