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
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      <TextField
        type="time"
        size="small"
        label={`Check-in reminder for ${name}`}
        value={time}
        onChange={(e) => onSetReminder(userId, e.target.value, enabled)}
        slotProps={{ inputLabel: { shrink: true } }}
      />
      <Switch
        checked={enabled}
        onChange={(e) => onSetReminder(userId, time || null, e.target.checked)}
        slotProps={{ input: { 'aria-label': `Enable check-in reminder for ${name}` } }}
      />
    </Box>
  );
}
