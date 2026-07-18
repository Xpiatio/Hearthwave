import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';

export interface IncidentReportPayload {
  category: string;
  description: string;
  location: string;
}

interface IncidentDialogProps {
  open: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: IncidentReportPayload) => void;
}

/** Plain-language incident categories. Values mirror
 *  backend/neighborhood/incidents.py CATEGORIES keys exactly — the server
 *  validates against that same set. Shared with IncidentLog's filter so the
 *  two never drift apart. */
export const INCIDENT_CATEGORIES: { value: string; label: string }[] = [
  { value: 'suspicious', label: 'Suspicious activity' },
  { value: 'hazard', label: 'Hazard' },
  { value: 'medical', label: 'Medical' },
  { value: 'lost', label: 'Lost pet or person' },
  { value: 'utility', label: 'Utility outage' },
];

/** Report-an-incident form, modeled on SpotReportDialog: a Select plus two
 *  required fields, submit disabled until valid, server error surfaced via
 *  the `error` prop. */
export function IncidentDialog({ open, error, onClose, onSubmit }: IncidentDialogProps) {
  const [category, setCategory] = useState(INCIDENT_CATEGORIES[0].value);
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');

  const valid = useMemo(
    () => description.trim().length > 0 && location.trim().length > 0,
    [description, location],
  );

  function handleSubmit() {
    if (!valid) return;
    onSubmit({ category, description: description.trim(), location: location.trim() });
    setDescription('');
    setLocation('');
    setCategory(INCIDENT_CATEGORIES[0].value);
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>Report an incident</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}

          <FormControl size="small" fullWidth>
            <InputLabel id="incident-category-label">Category</InputLabel>
            <Select
              labelId="incident-category-label"
              label="Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {INCIDENT_CATEGORIES.map((c) => (
                <MenuItem key={c.value} value={c.value}>{c.label}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            size="small"
            label="What happened?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            multiline
            minRows={2}
            required
          />

          <TextField
            size="small"
            label="Location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. corner of 5th and Main"
            required
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!valid}>
          Send report
        </Button>
      </DialogActions>
    </Dialog>
  );
}
