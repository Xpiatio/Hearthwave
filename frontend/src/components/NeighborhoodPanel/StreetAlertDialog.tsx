import { useState } from 'react';
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField } from '@mui/material';
import { ConfirmDialog } from '../ConfirmDialog';

const STREET_ALERT_MAX = 200;

export interface StreetAlertDialogProps {
  open: boolean;
  onClose: () => void;
  onSend: (message: string) => void;
}

/** The stacked view's inline street-alert field, in dialog form for the
 *  coordinator dashboard's command bar. Same 200-char cap, same explicit
 *  confirm step before anything goes out to every screen. */
export function StreetAlertDialog({ open, onClose, onSend }: StreetAlertDialogProps) {
  const [message, setMessage] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);

  function handleConfirm() {
    const trimmed = message.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setMessage('');
    onClose();
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Street alert</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              autoFocus
              fullWidth
              size="small"
              label="Street alert message"
              value={message}
              onChange={(e) => setMessage(e.target.value.slice(0, STREET_ALERT_MAX))}
              placeholder="e.g. Power out on Maple St, crews on the way"
              helperText={`${message.length}/${STREET_ALERT_MAX}`}
              slotProps={{ htmlInput: { maxLength: STREET_ALERT_MAX } }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            disabled={!message.trim()}
            onClick={() => setConfirmOpen(true)}
          >
            Send street alert
          </Button>
        </DialogActions>
      </Dialog>
      <ConfirmDialog
        open={confirmOpen}
        title="Send this alert to everyone?"
        body={message.trim()}
        confirmLabel="Yes, send the alert"
        destructive
        onConfirm={handleConfirm}
        onClose={() => setConfirmOpen(false)}
      />
    </>
  );
}
