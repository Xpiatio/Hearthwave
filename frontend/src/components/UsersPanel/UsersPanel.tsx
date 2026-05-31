import { useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import type { UserProfile } from '../../types/ws';

interface Props {
  profiles: UserProfile[];
  currentUserId: string;
  onCreateProfile: (data: {
    display_name: string;
    password: string;
    avatar_emoji: string;
    operator_name: string;
    callsign: string;
    location: string;
    is_admin: boolean;
  }) => void;
  onDeleteProfile: (userId: string) => void;
  onResetLockout: (userId: string) => void;
}

const EMOJI_OPTIONS = ['👤', '👨', '👩', '👦', '👧', '🧑', '👴', '👵', '🧔', '👮'];

export function UsersPanel({
  profiles,
  currentUserId,
  onCreateProfile,
  onDeleteProfile,
  onResetLockout,
}: Props) {
  const [createOpen, setCreateOpen] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [operatorName, setOperatorName] = useState('');
  const [callsign, setCallsign] = useState('');
  const [location, setLocation] = useState('');
  const [avatarEmoji, setAvatarEmoji] = useState('👤');
  const [isAdmin, setIsAdmin] = useState(false);
  const [formError, setFormError] = useState('');

  function openCreate() {
    setDisplayName('');
    setPassword('');
    setConfirmPw('');
    setOperatorName('');
    setCallsign('');
    setLocation('');
    setAvatarEmoji('👤');
    setIsAdmin(false);
    setFormError('');
    setCreateOpen(true);
  }

  function handleCreate() {
    if (!displayName.trim()) { setFormError('Display name is required.'); return; }
    if (password.length < 8) { setFormError('Password must be at least 8 characters.'); return; }
    if (password !== confirmPw) { setFormError('Passwords do not match.'); return; }
    onCreateProfile({
      display_name: displayName.trim(),
      password,
      avatar_emoji: avatarEmoji,
      operator_name: operatorName.trim() || displayName.trim(),
      callsign: callsign.trim().toUpperCase(),
      location: location.trim(),
      is_admin: isAdmin,
    });
    setCreateOpen(false);
  }

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>User Accounts</Typography>
        <Button startIcon={<AddIcon />} size="small" variant="outlined" onClick={openCreate}>
          New User
        </Button>
      </Box>

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>User</TableCell>
            <TableCell>Call Sign</TableCell>
            <TableCell>Role</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {profiles.map((p) => (
            <TableRow key={p.id}>
              <TableCell>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <span style={{ fontSize: '1.2rem' }}>{p.avatar_emoji}</span>
                  <Box>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{p.display_name}</Typography>
                    {p.operator_name !== p.display_name && (
                      <Typography variant="caption" sx={{ color: 'text.secondary' }}>{p.operator_name}</Typography>
                    )}
                  </Box>
                </Box>
              </TableCell>
              <TableCell>
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{p.callsign || '—'}</Typography>
              </TableCell>
              <TableCell>
                {p.is_admin && <Chip label="Admin" size="small" color="primary" variant="outlined" />}
              </TableCell>
              <TableCell align="right">
                <Tooltip title="Reset lockout">
                  <IconButton size="small" onClick={() => onResetLockout(p.id)}>
                    <LockOpenIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                {p.id !== currentUserId && (
                  <Tooltip title="Delete user">
                    <IconButton size="small" color="error" onClick={() => onDeleteProfile(p.id)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Create user dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>New User Account</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <Box>
              <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
                Avatar
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {EMOJI_OPTIONS.map((e) => (
                  <IconButton
                    key={e}
                    size="small"
                    onClick={() => setAvatarEmoji(e)}
                    sx={{
                      border: 2,
                      borderColor: avatarEmoji === e ? 'primary.main' : 'transparent',
                      borderRadius: 1,
                      fontSize: '1.2rem',
                    }}
                  >
                    {e}
                  </IconButton>
                ))}
              </Box>
            </Box>
            <TextField
              label="Display Name *"
              value={displayName}
              onChange={(e) => { setDisplayName(e.target.value); setFormError(''); }}
              fullWidth
              autoFocus
            />
            <TextField
              label="Operator Name"
              value={operatorName}
              onChange={(e) => setOperatorName(e.target.value)}
              fullWidth
              helperText="Name used in transmissions (defaults to display name)"
            />
            <TextField
              label="Call Sign"
              value={callsign}
              onChange={(e) => setCallsign(e.target.value.toUpperCase())}
              fullWidth
              slotProps={{ htmlInput: { style: { textTransform: 'uppercase' } } }}
            />
            <TextField
              label="Location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              fullWidth
            />
            <Divider />
            <TextField
              label="Password *"
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setFormError(''); }}
              fullWidth
              helperText="Minimum 8 characters"
            />
            <TextField
              label="Confirm Password *"
              type="password"
              value={confirmPw}
              onChange={(e) => { setConfirmPw(e.target.value); setFormError(''); }}
              fullWidth
              error={!!formError}
              helperText={formError}
            />
            <FormControlLabel
              control={<Checkbox checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} />}
              label="Admin (can change station settings and manage users)"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate}>Create</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
