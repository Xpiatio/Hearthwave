import { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  IconButton,
  InputLabel,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutlined';
import DeleteIcon from '@mui/icons-material/Delete';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import type { UserProfile } from '../../types/ws';

const MAX_PRESETS = 20;

type Role = 'admin' | 'adult' | 'kid';

const ROLE_LABELS: Record<Role, string> = {
  admin: 'Admin',
  adult: 'Adult',
  kid: 'Kid',
};

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
    role: Role;
  }) => void;
  onDeleteProfile: (userId: string) => void;
  onResetLockout: (userId: string) => void;
  onSetRole: (userId: string, role: Role) => void;
  onSetUserQuickMessages: (userId: string, quickMessages: string[]) => void;
}

const EMOJI_OPTIONS = ['👤', '👨', '👩', '👦', '👧', '🧑', '👴', '👵', '🧔', '👮'];

export function UsersPanel({
  profiles,
  currentUserId,
  onCreateProfile,
  onDeleteProfile,
  onResetLockout,
  onSetRole,
  onSetUserQuickMessages,
}: Props) {
  const [createOpen, setCreateOpen] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [operatorName, setOperatorName] = useState('');
  const [callsign, setCallsign] = useState('');
  const [location, setLocation] = useState('');
  const [avatarEmoji, setAvatarEmoji] = useState('👤');
  const [role, setRole] = useState<Role>('adult');
  const [formError, setFormError] = useState('');

  const [presetUser, setPresetUser] = useState<UserProfile | null>(null);
  const [presetDraftList, setPresetDraftList] = useState<string[]>([]);
  const [presetDraft, setPresetDraft] = useState('');

  function openPresets(p: UserProfile) {
    setPresetUser(p);
    setPresetDraftList(p.prefs?.quick_messages ?? []);
    setPresetDraft('');
  }

  function closePresets() {
    setPresetUser(null);
    setPresetDraftList([]);
    setPresetDraft('');
  }

  function handleAddPreset() {
    const trimmed = presetDraft.trim();
    if (!trimmed || presetDraftList.length >= MAX_PRESETS) return;
    setPresetDraftList((prev) => [...prev, trimmed]);
    setPresetDraft('');
  }

  function handleRemovePreset(idx: number) {
    setPresetDraftList((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleSavePresets() {
    if (!presetUser) return;
    onSetUserQuickMessages(presetUser.id, presetDraftList);
    closePresets();
  }

  const presetIsKid = presetUser?.role === 'kid';
  const presetHasBraces = presetDraftList.some((m) => m.includes('{') || m.includes('}'));
  // The server requires at least one preset for every role (min 1), so an empty
  // list is never savable — for a kid row this is also the safety-critical case
  // (no presets = nothing to transmit), hence the more specific helper text below.
  const presetSaveDisabled = presetDraftList.length === 0;

  function openCreate() {
    setDisplayName('');
    setPassword('');
    setConfirmPw('');
    setOperatorName('');
    setCallsign('');
    setLocation('');
    setAvatarEmoji('👤');
    setRole('adult');
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
      role,
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
                <Tooltip title={p.id === currentUserId ? "You can't change your own role." : ''}>
                  <span>
                    <Select
                      size="small"
                      value={p.role}
                      disabled={p.id === currentUserId}
                      onChange={(e: SelectChangeEvent) => onSetRole(p.id, e.target.value as Role)}
                      aria-label={`Role for ${p.display_name}`}
                    >
                      {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
                        <MenuItem key={r} value={r}>{ROLE_LABELS[r]}</MenuItem>
                      ))}
                    </Select>
                  </span>
                </Tooltip>
              </TableCell>
              <TableCell align="right">
                <Tooltip title={`Edit quick messages for ${p.display_name}`}>
                  <IconButton size="small" aria-label={`Edit quick messages for ${p.display_name}`} onClick={() => openPresets(p)}>
                    <ChatBubbleOutlineIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title={`Reset lockout for ${p.display_name}`}>
                  <IconButton size="small" aria-label={`Reset lockout for ${p.display_name}`} onClick={() => onResetLockout(p.id)}>
                    <LockOpenIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                {p.id !== currentUserId && (
                  <Tooltip title={`Delete user ${p.display_name}`}>
                    <IconButton size="small" color="error" aria-label={`Delete user ${p.display_name}`} onClick={() => onDeleteProfile(p.id)}>
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
                    onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); setAvatarEmoji(e); } }}
                    aria-label={`Select avatar ${e}`}
                    aria-pressed={avatarEmoji === e}
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
            <FormControl fullWidth>
              <InputLabel id="new-user-role-label">Role</InputLabel>
              <Select
                labelId="new-user-role-label"
                label="Role"
                value={role}
                onChange={(e: SelectChangeEvent) => setRole(e.target.value as Role)}
              >
                {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
                  <MenuItem key={r} value={r}>{ROLE_LABELS[r]}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate}>Create</Button>
        </DialogActions>
      </Dialog>

      {/* Edit quick-message presets dialog */}
      <Dialog open={presetUser !== null} onClose={closePresets} fullWidth maxWidth="sm">
        <DialogTitle>
          {presetUser ? `Quick Messages — ${presetUser.display_name}` : 'Quick Messages'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              These are the presets shown on this account's Family activity quick-message row.
              {presetIsKid && ' Kid accounts can only transmit these presets, and cannot use placeholders.'}
            </Typography>

            <List dense disablePadding>
              {presetDraftList.map((m, i) => (
                <ListItem
                  key={i}
                  disablePadding
                  sx={{ gap: 0.5 }}
                  secondaryAction={
                    <IconButton
                      size="small"
                      color="error"
                      aria-label={`Remove preset ${i + 1}`}
                      onClick={() => handleRemovePreset(i)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  }
                >
                  <ListItemText primary={m} slotProps={{ primary: { variant: 'body2' } }} sx={{ pr: 5 }} />
                </ListItem>
              ))}
              {presetDraftList.length === 0 && (
                <Typography variant="body2" sx={{ color: 'text.secondary', py: 1 }}>
                  No presets yet.
                </Typography>
              )}
            </List>

            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                size="small"
                fullWidth
                label="Add preset"
                value={presetDraft}
                onChange={(e) => setPresetDraft(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddPreset())}
                placeholder="New preset phrase…"
                disabled={presetDraftList.length >= MAX_PRESETS}
              />
              <Button
                variant="outlined"
                onClick={handleAddPreset}
                disabled={!presetDraft.trim() || presetDraftList.length >= MAX_PRESETS}
              >
                ADD
              </Button>
            </Box>

            {presetDraftList.length >= MAX_PRESETS && (
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Maximum of {MAX_PRESETS} presets.
              </Typography>
            )}

            {presetIsKid && presetHasBraces && (
              <Typography variant="caption" color="error">
                Kid presets cannot contain placeholders ({'{'} or {'}'}).
              </Typography>
            )}

            {presetIsKid && presetDraftList.length === 0 && (
              <Typography variant="caption" color="error">
                Kid accounts need at least one preset to transmit.
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={closePresets}>Cancel</Button>
          <Button variant="contained" onClick={handleSavePresets} disabled={presetSaveDisabled}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
