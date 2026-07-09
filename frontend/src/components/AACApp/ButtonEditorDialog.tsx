import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material';
import type { AACButton } from '../../types/aac';
import { newId } from './defaultGrid';

interface Props {
  open: boolean;
  /** null = creating a new button */
  button: AACButton | null;
  onSave: (button: AACButton) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

export function ButtonEditorDialog({ open, button, onSave, onDelete, onClose }: Props) {
  const [emoji, setEmoji] = useState('');
  const [label, setLabel] = useState('');
  const [text, setText] = useState('');

  useEffect(() => {
    if (open) {
      setEmoji(button?.emoji ?? '💬');
      setLabel(button?.label ?? '');
      setText(button?.text ?? '');
    }
  }, [open, button]);

  const valid = label.trim().length > 0;

  function handleSave() {
    if (!valid) return;
    onSave({
      id: button?.id ?? newId('b'),
      emoji: emoji.trim() || '💬',
      label: label.trim(),
      text: text.trim() || label.trim(),
    });
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{button ? 'Edit Button' : 'Add Button'}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField
            label="Emoji"
            value={emoji}
            onChange={(e) => setEmoji(e.target.value)}
            helperText="Pick one emoji for the button picture"
            slotProps={{ htmlInput: { maxLength: 8, style: { fontSize: '1.5rem' } } }}
          />
          <TextField
            label="Label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            required
            error={!valid}
            helperText={valid ? 'Short word shown on the button' : 'Label is required'}
          />
          <TextField
            label="Spoken text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            multiline
            minRows={2}
            helperText="Added to the message when tapped. Leave empty to use the label. {Name} and {callsign} are replaced automatically."
          />
          <Typography variant="body2" color="text.secondary">
            Preview: {emoji || '💬'} {label || '…'}
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        {button && (
          <Button
            color="error"
            onClick={() => {
              if (window.confirm(`Delete the "${button.label}" button?`)) {
                onDelete(button.id);
                onClose();
              }
            }}
          >
            DELETE
          </Button>
        )}
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose}>CANCEL</Button>
        <Button variant="contained" onClick={handleSave} disabled={!valid}>
          SAVE
        </Button>
      </DialogActions>
    </Dialog>
  );
}
