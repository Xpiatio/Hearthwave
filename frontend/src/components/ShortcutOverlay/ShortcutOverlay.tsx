import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography,
} from '@mui/material';

const SHORTCUTS: Array<[string, string]> = [
  ['?', 'Show or hide this shortcut list'],
  ['Esc', 'Back to home (closes the current activity)'],
  ['← ↑ → ↓', 'Move between cards on the home screen and AAC buttons'],
  ['Enter / Space', 'Open or press the focused card or button'],
  ['Tab', 'Move between controls'],
  ['Hold Space', 'Push-to-talk while the voice button is focused'],
];

export function ShortcutOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs" aria-labelledby="shortcut-overlay-title">
      <DialogTitle id="shortcut-overlay-title">Keyboard shortcuts</DialogTitle>
      <DialogContent>
        <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 1.5, m: 0 }}>
          {SHORTCUTS.map(([key, desc]) => (
            <Box key={key} sx={{ display: 'contents' }}>
              <Typography component="dt" sx={{ fontFamily: 'monospace', fontWeight: 700, whiteSpace: 'nowrap' }}>
                {key}
              </Typography>
              <Typography component="dd" sx={{ m: 0 }}>{desc}</Typography>
            </Box>
          ))}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>CLOSE</Button>
      </DialogActions>
    </Dialog>
  );
}
