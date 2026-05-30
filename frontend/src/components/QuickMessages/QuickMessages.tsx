import { useState, useEffect } from 'react';
import {
  Box,
  Button,
  IconButton,
  Typography,
  TextField,
  List,
  ListItem,
  ListItemText,
  Tooltip,
  Paper,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckIcon from '@mui/icons-material/Check';

const STORAGE_KEY = 'radio_tty_quick_messages';
const DEFAULTS = ['Standing by', 'QSL', 'Copy that', 'QSY to channel {N}', 'Good signal'];

function load(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed as string[];
    }
  } catch {
    // ignore
  }
  return DEFAULTS.slice();
}

function save(phrases: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(phrases));
}

interface Props {
  operatorName: string;
  onSelect: (text: string) => void;
}

export function QuickMessages({ operatorName, onSelect }: Props) {
  const [phrases, setPhrases] = useState<string[]>(load);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  useEffect(() => {
    save(phrases);
  }, [phrases]);

  function handleSelect(phrase: string) {
    const text = phrase.replace(/{Name}/gi, operatorName || 'Operator');
    onSelect(text);
  }

  function handleAdd() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    setPhrases((prev) => [...prev, trimmed]);
    setDraft('');
  }

  function handleRemove(idx: number) {
    setPhrases((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleMoveUp(idx: number) {
    if (idx === 0) return;
    setPhrases((prev) => {
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
  }

  function handleMoveDown(idx: number) {
    setPhrases((prev) => {
      if (idx >= prev.length - 1) return prev;
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next;
    });
  }

  if (editing) {
    return (
      <Paper square elevation={0} sx={{ borderTop: 1, borderColor: 'divider', p: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>QUICK MESSAGES</Typography>
          <Button
            size="small"
            variant="contained"
            startIcon={<CheckIcon />}
            onClick={() => setEditing(false)}
          >
            DONE
          </Button>
        </Box>

        <List dense disablePadding>
          {phrases.map((p, i) => (
            <ListItem
              key={i}
              disablePadding
              sx={{ gap: 0.5 }}
              secondaryAction={
                <Box sx={{ display: 'flex', gap: 0.25 }}>
                  <IconButton size="small" onClick={() => handleMoveUp(i)} disabled={i === 0}
                    aria-label="Move up">
                    <ArrowUpwardIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" onClick={() => handleMoveDown(i)}
                    disabled={i === phrases.length - 1} aria-label="Move down">
                    <ArrowDownwardIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" onClick={() => handleRemove(i)} color="error"
                    aria-label="Remove">
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Box>
              }
            >
              <ListItemText
                primary={p}
                slotProps={{ primary: { variant: 'body2' } }}
                sx={{ pr: 13 }}
              />
            </ListItem>
          ))}
        </List>

        <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
          <TextField
            size="small"
            fullWidth
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="New phrase… use {Name} for operator name"
            label="Add phrase"
          />
          <Button variant="outlined" onClick={handleAdd} disabled={!draft.trim()}>
            ADD
          </Button>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper square elevation={0} sx={{ borderTop: 1, borderColor: 'divider', px: 1, py: 0.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Box
          sx={{
            display: 'flex',
            flex: 1,
            gap: 0.5,
            overflowX: 'auto',
            pb: 0.25,
            '&::-webkit-scrollbar': { height: 4 },
          }}
        >
          {phrases.map((p, i) => (
            <Button
              key={i}
              size="small"
              variant="outlined"
              onClick={() => handleSelect(p)}
              title={p}
              sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}
            >
              {p.replace(/{Name}/gi, operatorName || 'Operator')}
            </Button>
          ))}
        </Box>

        <Tooltip title="Edit quick messages">
          <IconButton
            size="small"
            onClick={() => setEditing(true)}
            aria-label="Edit quick messages"
          >
            <SettingsIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    </Paper>
  );
}
