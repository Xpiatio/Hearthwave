import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
} from '@mui/material';

interface Props {
  open: boolean;
  tokens: string[];
  originalText: string;
  onSubmit: (resolvedText: string) => void;
  onCancel: () => void;
}

export function TokenPromptDialog({ open, tokens, originalText, onSubmit, onCancel }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});

  const allFilled = tokens.every((t) => (values[t] ?? '').trim().length > 0);

  function handleSubmit() {
    if (!allFilled) return;
    let resolved = originalText;
    for (const token of tokens) {
      resolved = resolved.replaceAll(`{${token}}`, values[token] ?? '');
    }
    onSubmit(resolved);
    setValues({});
  }

  function handleKeyDown(e: React.KeyboardEvent, isLast: boolean) {
    if (isLast && e.key === 'Enter' && allFilled) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleCancel() {
    setValues({});
    onCancel();
  }

  return (
    <Dialog open={open} onClose={handleCancel} aria-labelledby="token-prompt-title" maxWidth="xs" fullWidth>
      <DialogTitle id="token-prompt-title">Fill in message placeholders</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {tokens.map((token, i) => (
            <TextField
              key={token}
              label={`Value for {${token}}`}
              value={values[token] ?? ''}
              onChange={(e) => setValues((prev) => ({ ...prev, [token]: e.target.value }))}
              onKeyDown={(e) => handleKeyDown(e, i === tokens.length - 1)}
              autoFocus={i === 0}
              fullWidth
            />
          ))}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCancel}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!allFilled}>
          Send
        </Button>
      </DialogActions>
    </Dialog>
  );
}
