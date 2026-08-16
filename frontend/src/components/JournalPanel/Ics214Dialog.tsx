import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TextField,
  Button,
  Box,
} from '@mui/material';
import type { Ics214Header } from '../../netsessions/ics214';

/** Remembered between exports: an activation runs many nets, and retyping the
 *  agency and position on each one is how a form ends up half-filled. */
const STORAGE_KEY = 'radio_tty_ics214_header';

const EMPTY: Ics214Header = {
  incidentName: '',
  preparedByName: '',
  preparedByPosition: 'Net Control Station',
  homeAgency: '',
};

function loadHeader(): Ics214Header {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    const saved = JSON.parse(raw) as Partial<Ics214Header>;
    return { ...EMPTY, ...saved };
  } catch {
    return EMPTY;
  }
}

function saveHeader(header: Ics214Header) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(header));
  } catch {
    // A full or blocked localStorage must not cost the operator the export.
  }
}

interface Props {
  open: boolean;
  onExport: (header: Ics214Header) => void;
  onCancel: () => void;
}

export function Ics214Dialog({ open, onExport, onCancel }: Props) {
  const [header, setHeader] = useState<Ics214Header>(EMPTY);

  // Re-read on each open so a value saved by a previous export shows up, and
  // so an abandoned edit never carries into the next one.
  useEffect(() => {
    if (open) setHeader(loadHeader());
  }, [open]);

  const canExport =
    header.incidentName.trim().length > 0 && header.preparedByName.trim().length > 0;

  function field(key: keyof Ics214Header, label: string, required = false) {
    return (
      <TextField
        label={label}
        required={required}
        value={header[key]}
        onChange={(e) => setHeader((prev) => ({ ...prev, [key]: e.target.value }))}
        autoFocus={key === 'incidentName'}
        fullWidth
      />
    );
  }

  function handleExport() {
    if (!canExport) return;
    saveHeader(header);
    onExport(header);
  }

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      aria-labelledby="ics214-title"
      maxWidth="xs"
      fullWidth
    >
      <DialogTitle id="ics214-title">ICS-214 activity log</DialogTitle>
      <DialogContent>
        <DialogContentText variant="body2" sx={{ mb: 2 }}>
          These boxes aren't part of a net record, so fill them in here. The
          operational period, resources and activity log come from the session.
        </DialogContentText>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {field('incidentName', 'Incident name', true)}
          {field('preparedByName', 'Prepared by (name)', true)}
          {field('preparedByPosition', 'ICS position')}
          {field('homeAgency', 'Home agency (and unit)')}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="contained" onClick={handleExport} disabled={!canExport}>
          Export
        </Button>
      </DialogActions>
    </Dialog>
  );
}
