import { Box, Button, Typography } from '@mui/material';

export interface PresetComposerProps {
  quickMessages: string[];
  onSend: (text: string, targetCall: string, targetName: string) => void;
}

/** Kid-mode composer: replaces the free-text MessageInput with a row of
 *  admin-set preset buttons. Sends each preset's text byte-for-byte, with
 *  no trimming or decoration — the server gates a kid account's TX to an
 *  exact match against this same quick_messages list (see server.py
 *  `_is_kid` tx_message handling), so any alteration here would make every
 *  kid send fail server-side.
 *
 *  A kid whose admin hasn't set up any presets yet has an empty
 *  quick_messages list — every message they could send would be rejected
 *  server-side, so render an explanatory empty state instead of a dead
 *  zero-button row. */
export function PresetComposer({ quickMessages, onSend }: PresetComposerProps) {
  if (quickMessages.length === 0) {
    return (
      <Box role="group" aria-label="Quick messages" sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Ask an adult to set up your messages.
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      role="group"
      aria-label="Quick messages"
      sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, p: 1 }}
    >
      {quickMessages.map((text) => (
        <Button
          key={text}
          variant="contained"
          onClick={() => onSend(text, '', '')}
          sx={{ minHeight: 56, textTransform: 'none' }}
        >
          {text}
        </Button>
      ))}
    </Box>
  );
}
