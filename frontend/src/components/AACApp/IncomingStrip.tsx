import { Box, Paper, Typography } from '@mui/material';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';

interface Props {
  messages: ChatEntry[];
}

const SHOWN = 3;

const KIND_LABEL: Record<string, string> = {
  rx: 'Heard',
  tx: 'Sent',
  chat: 'Chat',
  system: 'System',
};

export function IncomingStrip({ messages }: Props) {
  const recent = messages.slice(-SHOWN);
  return (
    <Paper
      square
      elevation={0}
      aria-label="Recent messages"
      sx={{ borderBottom: 1, borderColor: 'divider', px: 1.5, py: 0.75 }}
    >
      <Box aria-live="polite" aria-atomic="false">
        {recent.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No messages yet
          </Typography>
        ) : (
          recent.map((m) => (
            <Typography key={m.id} variant="body2" noWrap sx={{ opacity: m.partial ? 0.6 : 1 }}>
              <Typography component="span" variant="body2" sx={{ fontWeight: 700, mr: 0.5 }}>
                {KIND_LABEL[m.kind] ?? m.kind}
                {m.sender ? ` · ${m.sender}` : ''}:
              </Typography>
              {m.text}
            </Typography>
          ))
        )}
      </Box>
    </Paper>
  );
}
