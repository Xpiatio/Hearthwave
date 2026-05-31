import { useState, useEffect } from 'react';
import {
  Avatar,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import EditIcon from '@mui/icons-material/Edit';
import LockIcon from '@mui/icons-material/Lock';
import type { UserProfile } from '../../types/ws';

interface Props {
  profile: UserProfile;
  onUpdateProfile: (updates: {
    operator_name?: string;
    callsign?: string;
    location?: string;
    avatar_emoji?: string;
  }) => void;
  onChangePassword: (newPassword: string) => void;
  onLogout: () => void;
}

const EMOJI_OPTIONS = ['👤', '👨', '👩', '👦', '👧', '🧑', '👴', '👵', '🧔', '👮'];

export function AccountMenu({ profile, onUpdateProfile, onChangePassword, onLogout }: Props) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);

  const [operatorName, setOperatorName] = useState(profile.operator_name);
  const [callsign, setCallsign] = useState(profile.callsign);
  const [location, setLocation] = useState(profile.location);
  const [avatarEmoji, setAvatarEmoji] = useState(profile.avatar_emoji);

  // Sync form fields when profile updates from the server, but only while
  // the edit dialog is closed so we don't clobber in-progress edits.
  useEffect(() => {
    if (!editOpen) {
      setOperatorName(profile.operator_name);
      setCallsign(profile.callsign);
      setLocation(profile.location);
      setAvatarEmoji(profile.avatar_emoji);
    }
  }, [profile, editOpen]);

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pwError, setPwError] = useState('');

  function handleOpen(e: React.MouseEvent<HTMLElement>) {
    setAnchorEl(e.currentTarget);
  }

  function handleClose() {
    setAnchorEl(null);
  }

  function openEdit() {
    setOperatorName(profile.operator_name);
    setCallsign(profile.callsign);
    setLocation(profile.location);
    setAvatarEmoji(profile.avatar_emoji);
    setEditOpen(true);
    handleClose();
  }

  function openPw() {
    setNewPassword('');
    setConfirmPassword('');
    setPwError('');
    setPwOpen(true);
    handleClose();
  }

  function handleEditSave() {
    onUpdateProfile({
      operator_name: operatorName.trim(),
      callsign: callsign.trim().toUpperCase(),
      location: location.trim(),
      avatar_emoji: avatarEmoji,
    });
    setEditOpen(false);
  }

  function handlePwSave() {
    if (newPassword.length < 8) { setPwError('Password must be at least 8 characters.'); return; }
    if (newPassword !== confirmPassword) { setPwError('Passwords do not match.'); return; }
    onChangePassword(newPassword);
    setPwOpen(false);
  }

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        onClick={handleOpen}
        aria-label="Account menu"
        sx={{ gap: 0.75, textTransform: 'none', fontWeight: 600 }}
      >
        <Avatar sx={{ width: 22, height: 22, fontSize: '0.85rem', bgcolor: 'primary.main' }}>
          {profile.avatar_emoji}
        </Avatar>
        {profile.display_name}
      </Button>

      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleClose}>
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 700 }}>{profile.display_name}</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{profile.callsign || 'No call sign set'}</Typography>
        </Box>
        <Divider />
        <MenuItem onClick={openEdit}>
          <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
          Edit Profile
        </MenuItem>
        <MenuItem onClick={openPw}>
          <ListItemIcon><LockIcon fontSize="small" /></ListItemIcon>
          Change Password
        </MenuItem>
        <Divider />
        <MenuItem onClick={() => { handleClose(); onLogout(); }}>
          <ListItemIcon><LogoutIcon fontSize="small" /></ListItemIcon>
          Sign Out
        </MenuItem>
      </Menu>

      {/* Edit profile dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Edit Profile</DialogTitle>
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
            <TextField label="Operator Name" value={operatorName} onChange={(e) => setOperatorName(e.target.value)} fullWidth />
            <TextField
              label="Call Sign"
              value={callsign}
              onChange={(e) => setCallsign(e.target.value.toUpperCase())}
              fullWidth
              slotProps={{ htmlInput: { style: { textTransform: 'uppercase' } } }}
            />
            <TextField label="Location" value={location} onChange={(e) => setLocation(e.target.value)} fullWidth />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleEditSave}>Save</Button>
        </DialogActions>
      </Dialog>

      {/* Change password dialog */}
      <Dialog open={pwOpen} onClose={() => setPwOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Change Password</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => { setNewPassword(e.target.value); setPwError(''); }}
              fullWidth
              autoFocus
            />
            <TextField
              label="Confirm New Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => { setConfirmPassword(e.target.value); setPwError(''); }}
              fullWidth
              error={!!pwError}
              helperText={pwError}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPwOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handlePwSave} disabled={!newPassword || !confirmPassword}>
            Change
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
