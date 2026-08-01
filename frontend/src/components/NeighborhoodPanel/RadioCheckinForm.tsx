import { useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import type { Contact } from '../../types/ws';

export interface RadioCheckinFormProps {
  contacts: Contact[];
  onCheckin: (p: { callsign: string; name: string; location: string; saveContact: boolean }) => void;
}

const CALLSIGN_MAX = 16;
const NAME_MAX = 64;
const LOCATION_MAX = 64;

/** Coordinator-side check-in for a neighbor who called in on the radio and has
 *  no account here.
 *
 *  A Select over known contacts rather than an Autocomplete: a household's
 *  contact book is short, and the codebase has no Autocomplete anywhere else
 *  to be consistent with. Picking a contact only prefills — every field stays
 *  editable, because the point is to also handle the neighbor who has never
 *  called in before.
 *
 *  "Save to contacts" appears only for an unknown callsign, and matters more
 *  than it looks: attendance history keys on (callsign, name), so a name typed
 *  slightly differently each week fragments a regular's streak. Saving makes
 *  next week a pick instead of a retype. */
export function RadioCheckinForm({ contacts, onCheckin }: RadioCheckinFormProps) {
  const [picked, setPicked] = useState('');
  const [callsign, setCallsign] = useState('');
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [saveContact, setSaveContact] = useState(false);

  const normalized = callsign.trim().toUpperCase();
  const known = contacts.some((c) => (c.callsign || '').toUpperCase() === normalized);
  const canSubmit = normalized.length > 0 && name.trim().length > 0;

  function handlePick(value: string) {
    setPicked(value);
    const contact = contacts.find((c) => c.callsign === value);
    if (!contact) return;
    setCallsign(contact.callsign || '');
    setName(contact.name || '');
    setLocation(contact.location || '');
    setSaveContact(false);
  }

  function handleSubmit() {
    if (!canSubmit) return;
    onCheckin({
      callsign: normalized,
      name: name.trim(),
      location: location.trim(),
      // A known callsign never writes a contact, whatever the box last held.
      saveContact: saveContact && !known,
    });
    setPicked('');
    setCallsign('');
    setName('');
    setLocation('');
    setSaveContact(false);
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
        Check in a radio caller
      </Typography>

      <FormControl size="small" sx={{ maxWidth: 320 }}>
        <InputLabel id="radio-checkin-contact-label">Pick a neighbor</InputLabel>
        <Select
          labelId="radio-checkin-contact-label"
          label="Pick a neighbor"
          value={picked}
          onChange={(e) => handlePick(e.target.value)}
        >
          <MenuItem value="">Someone new</MenuItem>
          {contacts.map((c) => (
            <MenuItem key={c.callsign} value={c.callsign}>
              {c.callsign} — {c.name || 'unnamed'}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Callsign"
          value={callsign}
          onChange={(e) => setCallsign(e.target.value.slice(0, CALLSIGN_MAX))}
          slotProps={{ htmlInput: { maxLength: CALLSIGN_MAX } }}
          sx={{ width: 160 }}
        />
        <TextField
          size="small"
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value.slice(0, NAME_MAX))}
          slotProps={{ htmlInput: { maxLength: NAME_MAX } }}
          sx={{ width: 200 }}
        />
        <TextField
          size="small"
          label="Location"
          value={location}
          onChange={(e) => setLocation(e.target.value.slice(0, LOCATION_MAX))}
          slotProps={{ htmlInput: { maxLength: LOCATION_MAX } }}
          sx={{ width: 200 }}
        />
      </Box>

      {normalized.length > 0 && !known && (
        <FormControlLabel
          control={
            <Checkbox
              checked={saveContact}
              onChange={(e) => setSaveContact(e.target.checked)}
            />
          }
          label="Save to contacts"
        />
      )}

      <Button
        variant="outlined"
        onClick={handleSubmit}
        disabled={!canSubmit}
        sx={{ alignSelf: 'flex-start' }}
      >
        Check in station
      </Button>
    </Box>
  );
}
