import { Button, Dialog, DialogActions, DialogTitle } from '@mui/material';
import type { FamilyPresenceEntry } from '../../types/ws';

export interface ConfirmOkDialogProps {
  /** The tapped presence entry, or null when the dialog should be closed. */
  entry: FamilyPresenceEntry | null;
  onConfirm: (entry: FamilyPresenceEntry) => void;
  onClose: () => void;
}

/** AAC huge-confirm pattern (design spec §4): "Mark {name} as OK?" with a
 *  pair of oversized Yes/No buttons sized for low dexterity/low vision taps
 *  on a wall-mounted kiosk. */
export function ConfirmOkDialog({ entry, onConfirm, onClose }: ConfirmOkDialogProps) {
  const open = entry !== null;

  function handleYes() {
    if (entry) onConfirm(entry);
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose}>
      {entry && <DialogTitle>Mark {entry.display_name} as OK?</DialogTitle>}
      <DialogActions sx={{ display: 'flex', gap: 2, p: 2 }}>
        <Button
          variant="contained"
          color="success"
          onClick={handleYes}
          sx={{ minHeight: 96, fontSize: '1.6rem', flex: 1 }}
        >
          Yes
        </Button>
        <Button
          variant="outlined"
          onClick={onClose}
          sx={{ minHeight: 96, fontSize: '1.6rem', flex: 1 }}
        >
          No
        </Button>
      </DialogActions>
    </Dialog>
  );
}
