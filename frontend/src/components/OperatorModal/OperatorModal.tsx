import { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
} from '@mui/material';
import type { Operator } from '../../hooks/useOperator';

interface Props {
  initial: Operator | null;
  onSave: (op: Operator) => void;
  onClose?: () => void;
}

export function OperatorModal({ initial, onSave, onClose }: Props) {
  const [operatorName, setOperatorName] = useState(initial?.operatorName ?? '');
  const [callsign, setCallsign] = useState(initial?.callsign ?? '');
  const [location, setLocation] = useState(initial?.location ?? '');
  const firstInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstInputRef.current?.focus();
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!operatorName.trim() || !callsign.trim()) return;
    onSave({ operatorName: operatorName.trim(), callsign: callsign.trim(), location: location.trim() });
  }

  const canSave = operatorName.trim().length > 0 && callsign.trim().length > 0;

  return (
    <Dialog
      open
      fullWidth
      maxWidth="sm"
      aria-labelledby="operator-dialog-title"
      onClose={(_event, reason) => {
        if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
          if (onClose) onClose();
        }
      }}
    >
      <DialogTitle id="operator-dialog-title">Operator Profile</DialogTitle>

      <DialogContent>
        <Box
          component="form"
          id="operator-form"
          onSubmit={handleSubmit}
          noValidate
          sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 0.5 }}
        >
          <TextField
            inputRef={firstInputRef}
            id="op-name"
            label="Operator Name *"
            value={operatorName}
            onChange={(e) => setOperatorName(e.target.value)}
            required
            autoComplete="name"
            placeholder="e.g. Grandma"
            fullWidth
          />
          <TextField
            id="op-callsign"
            label="FCC Call Sign *"
            value={callsign}
            onChange={(e) => setCallsign(e.target.value.toUpperCase())}
            required
            autoComplete="off"
            placeholder="e.g. WRFN123"
            fullWidth
            slotProps={{ htmlInput: { style: { textTransform: 'uppercase' } } }}
          />
          <TextField
            id="op-location"
            label="Location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            autoComplete="off"
            placeholder="e.g. Home Base"
            fullWidth
          />
        </Box>
      </DialogContent>

      <DialogActions>
        {onClose && (
          <Button onClick={onClose} color="inherit">
            Cancel
          </Button>
        )}
        <Button
          type="submit"
          form="operator-form"
          variant="contained"
          disabled={!canSave}
        >
          Save Profile
        </Button>
      </DialogActions>
    </Dialog>
  );
}
