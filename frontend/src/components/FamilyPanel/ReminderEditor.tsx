import { Box, Switch, TextField } from '@mui/material';

interface Props {
  userId: string;
  name: string;
  time: string;
  enabled: boolean;
  onSetReminder: (userId: string, time: string | null, enabled: boolean) => void;
}

/** Admin-only per-member check-in reminder control: a time picker plus an
 *  enable/disable switch. Every change saves immediately (no separate
 *  save step) via onSetReminder. */
export function ReminderEditor({ userId, name, time, enabled, onSetReminder }: Props) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
      <TextField
        type="time"
        size="small"
        label={`Check-in reminder for ${name}`}
        value={time}
        onChange={(e) => onSetReminder(userId, e.target.value || null, enabled)}
        slotProps={{ inputLabel: { shrink: true } }}
        // An outlined time input sizes to its content (~145px), and MUI caps a
        // shrunk label at calc(133% - 32px) with an ellipsis — which ate the
        // member name off the end of the label. Let the field claim the row's
        // spare width so the label has room; the cap keeps it from stretching
        // across a wide desktop, and minWidth holds a floor once the row wraps.
        sx={{ flex: '1 1 auto', minWidth: 280, maxWidth: 560 }}
      />
      <Switch
        checked={enabled}
        onChange={(e) => onSetReminder(userId, time || null, e.target.checked)}
        slotProps={{ input: { 'aria-label': `Enable check-in reminder for ${name}` } }}
      />
    </Box>
  );
}
