import { useState, useRef, forwardRef, useImperativeHandle } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
} from '@mui/material';
import type { Contact } from '../../types/ws';

export interface MessageInputHandle {
  setText: (text: string) => void;
}

interface Props {
  transmitting: boolean;
  contacts: Contact[];
  onSend: (text: string, targetCall: string, targetName: string) => void;
  onStandaloneId?: () => void;
}

export const MessageInput = forwardRef<MessageInputHandle, Props>(
  ({ transmitting, contacts, onSend, onStandaloneId }, ref) => {
    const [draft, setDraft] = useState('');
    const [targetKey, setTargetKey] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useImperativeHandle(ref, () => ({
      setText(text: string) {
        setDraft(text);
        textareaRef.current?.focus();
      },
    }));

    const sortedContacts = [...contacts].sort((a, b) =>
      a.callsign.toUpperCase().localeCompare(b.callsign.toUpperCase())
    );
    const contactKey = (c: Contact) => `${c.callsign}||${c.name ?? ''}`;
    const selectedContact = sortedContacts.find((c) => contactKey(c) === targetKey);

    function handleSend() {
      const text = draft.trim();
      if (!text || transmitting) return;
      onSend(
        text,
        selectedContact ? selectedContact.callsign : 'ALL',
        selectedContact ? (selectedContact.name ?? '') : '',
      );
      setDraft('');
      setTargetKey('');
      textareaRef.current?.focus();
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSend();
      }
    }

    return (
      <Paper elevation={3} square sx={{ p: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
        {transmitting && (
          <Alert severity="warning" role="alert" aria-live="assertive" icon={false}>
            SENDING MESSAGE NOW… PLEASE WAIT
          </Alert>
        )}

        {sortedContacts.length > 0 && (
          <FormControl size="small" fullWidth>
            <InputLabel id="target-label">To</InputLabel>
            <Select
              labelId="target-label"
              label="To"
              value={targetKey}
              onChange={(e) => setTargetKey(e.target.value)}
              disabled={transmitting}
            >
              <MenuItem value="">ALL — Broadcast</MenuItem>
              {sortedContacts.map((c) => (
                <MenuItem key={contactKey(c)} value={contactKey(c)}>
                  {c.callsign}{c.name ? ` — ${c.name}` : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        {selectedContact && (
          <Typography variant="body2" color="text.secondary" aria-live="polite">
            Calling {selectedContact.callsign}
            {selectedContact.name ? ` (${selectedContact.name})` : ''}
            {selectedContact.location ? ` · ${selectedContact.location}` : ''}
          </Typography>
        )}

        <TextField
          inputRef={textareaRef}
          label="Type Your Message Below"
          multiline
          rows={2}
          fullWidth
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={transmitting}
          placeholder={transmitting ? '' : 'Enter your message here… (Ctrl+Enter to send)'}
          slotProps={{
            htmlInput: {
              'aria-label': 'Message text — press Ctrl+Enter or use the Send button to transmit',
            },
          }}
        />

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={handleSend}
            disabled={transmitting || !draft.trim()}
            aria-label="Press to send message over radio"
          >
            PRESS TO SEND MESSAGE
          </Button>
          {onStandaloneId && (
            <Button
              variant="outlined"
              size="large"
              onClick={onStandaloneId}
              disabled={transmitting}
              aria-label="Transmit standalone station identification"
              sx={{ whiteSpace: 'nowrap' }}
            >
              THIS IS
            </Button>
          )}
        </Box>
      </Paper>
    );
  }
);

MessageInput.displayName = 'MessageInput';
