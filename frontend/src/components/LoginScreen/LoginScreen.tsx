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
} from '@mui/material';
import type { AuthError } from '../../hooks/useAuth';

interface Props {
  onLogin: (displayName: string, password: string) => Promise<unknown>;
}

export function LoginScreen({ onLogin }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [lockedUntil, setLockedUntil] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username || !password) return;
    setLoading(true);
    setError(null);
    setLockedUntil(null);
    try {
      await onLogin(username, password);
    } catch (err: unknown) {
      const status = (err as Partial<AuthError>)?.status;
      const detail = (err as Partial<AuthError>)?.detail ?? '';
      if (status === 423) {
        const match = detail.match(/(\d{4}-\d{2}-\d{2}T[\d:.+Z-]+)/);
        if (match) {
          try {
            const dt = new Date(match[1]);
            setLockedUntil(dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
          } catch {
            setLockedUntil('a short time');
          }
        } else {
          setLockedUntil('a short time');
        }
      } else if (status === 401) {
        setError('Invalid credentials. Please try again.');
      } else {
        setError('Could not reach the server. Check your connection and try again.');
      }
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
      <Card sx={{ width: '100%', maxWidth: 420 }} elevation={4}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5, textAlign: 'center' }}>
            Radio-TTY
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center', mb: 3 }}>
            Sign in to continue
          </Typography>

          <Box component="form" onSubmit={handleSubmit} noValidate>
            <TextField
              label="Username"
              value={username}
              onChange={(e) => { setUsername(e.target.value); setError(null); }}
              fullWidth
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
              autoComplete="current-password"
              sx={{ mb: 2 }}
            />

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            {lockedUntil && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                Account locked until {lockedUntil}. Contact an admin to reset.
              </Alert>
            )}

            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={!username || !password || loading}
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
