import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Avatar,
  Tooltip,
} from '@mui/material';
import type { AuthError } from '../../hooks/useAuth';

interface Props {
  onLogin: (displayName: string, password: string) => Promise<unknown>;
}

interface PublicProfile {
  id: string;
  display_name: string;
  avatar_emoji: string;
}

export function LoginScreen({ onLogin }: Props) {
  const [profiles, setProfiles] = useState<PublicProfile[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [lockedUntil, setLockedUntil] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch('/auth/profiles')
      .then((r) => r.ok ? r.json() : [])
      .then((data: PublicProfile[]) => setProfiles(data))
      .catch(() => {});
  }, []);

  function handleSelectProfile(displayName: string) {
    setSelected(displayName);
    setError(null);
    setLockedUntil(null);
    setPassword('');
    setTimeout(() => passwordRef.current?.focus(), 50);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || !password) return;
    setLoading(true);
    setError(null);
    setLockedUntil(null);
    try {
      await onLogin(selected, password);
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
            Select your profile to sign in
          </Typography>

          {/* Profile picker */}
          {profiles.length > 0 && (
            <Box sx={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: 1, justifyContent: 'center', mb: 3 }}>
              {profiles.map((p) => (
                <Tooltip key={p.id} title={p.display_name}>
                  <Box
                    onClick={() => handleSelectProfile(p.display_name)}
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      cursor: 'pointer',
                      gap: 0.5,
                      p: 1,
                      borderRadius: 2,
                      border: 2,
                      borderColor: selected === p.display_name ? 'primary.main' : 'transparent',
                      bgcolor: selected === p.display_name ? 'action.selected' : 'transparent',
                      transition: 'all 0.15s',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                  >
                    <Avatar sx={{ width: 48, height: 48, fontSize: '1.5rem', bgcolor: 'primary.light' }}>
                      {p.avatar_emoji}
                    </Avatar>
                    <Typography variant="caption" sx={{ fontWeight: selected === p.display_name ? 700 : 400 }}>
                      {p.display_name}
                    </Typography>
                  </Box>
                </Tooltip>
              ))}
            </Box>
          )}

          {/* Login form */}
          <Box component="form" onSubmit={handleSubmit} noValidate>
            {profiles.length === 0 && (
              <TextField
                label="Display Name"
                value={selected}
                onChange={(e) => { setSelected(e.target.value); setError(null); }}
                fullWidth
                autoFocus
                sx={{ mb: 2 }}
              />
            )}
            <TextField
              inputRef={passwordRef}
              label="Password"
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(null); }}
              fullWidth
              disabled={!selected}
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
              disabled={!selected || !password || loading}
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
