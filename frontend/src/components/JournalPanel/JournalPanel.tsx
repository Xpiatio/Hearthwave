import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  IconButton,
  Alert,
  TextField,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import PublishIcon from '@mui/icons-material/Publish';
import UnpublishedIcon from '@mui/icons-material/Unpublished';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { JournalEntry } from '../../types/ws';

interface JournalResultDraft {
  title: string;
  summary: string;
  callsigns_locations: Array<{ callsign: string; location: string }>;
}

interface Props {
  journals: JournalEntry[];
  pendingResult: JournalResultDraft | null;
  generating: boolean;
  journalError: string | null;
  rxTexts: string[];
  rxCallsigns: string[];
  onListJournals: () => void;
  onGenerate: (transcript: string, callsigns: string[]) => void;
  onSave: (title: string, summary: string, callsigns_locations: Array<{ callsign: string; location: string }>, transcript: string) => void;
  onDelete: (file_path: string) => void;
  onPublish: (file_path: string) => void;
  onUnpublish: (file_path: string) => void;
  onDismissResult: () => void;
}

function CallsignsTable({ rows }: { rows: Array<{ callsign: string; location: string }> }) {
  return (
    <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 700 }}>Callsign</TableCell>
            <TableCell sx={{ fontWeight: 700 }}>Location</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((cl) => (
            <TableRow key={cl.callsign}>
              <TableCell>{cl.callsign}</TableCell>
              <TableCell>{cl.location}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function JournalPanel({
  journals,
  pendingResult,
  generating,
  journalError,
  rxTexts,
  rxCallsigns,
  onListJournals,
  onGenerate,
  onSave,
  onDelete,
  onPublish,
  onUnpublish,
  onDismissResult,
}: Props) {
  const [selected, setSelected] = useState<JournalEntry | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editSummary, setEditSummary] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [confirmPublish, setConfirmPublish] = useState<string | null>(null);
  const [confirmUnpublish, setConfirmUnpublish] = useState<string | null>(null);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unpublishTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    onListJournals();
  }, [onListJournals]);

  useEffect(() => {
    return () => {
      if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
      if (unpublishTimerRef.current) clearTimeout(unpublishTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (pendingResult) {
      setEditTitle(pendingResult.title);
      setEditSummary(pendingResult.summary);
    }
  }, [pendingResult]);

  function handleGenerate() {
    onGenerate(rxTexts.join('\n'), rxCallsigns);
  }

  function handleSave() {
    if (!pendingResult) return;
    onSave(editTitle, editSummary, pendingResult.callsigns_locations, rxTexts.join('\n'));
    onDismissResult();
  }

  function handleDelete(file: string) {
    if (confirmDelete === file) {
      onDelete(file);
      setConfirmDelete(null);
      if (selected?._file === file) setSelected(null);
    } else {
      setConfirmDelete(file);
    }
  }

  function handlePublish(file: string) {
    if (confirmPublish === file) {
      onPublish(file);
      setConfirmPublish(null);
      if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
    } else {
      setConfirmPublish(file);
      if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
      resetTimerRef.current = setTimeout(() => setConfirmPublish((cur) => cur === file ? null : cur), 4000);
    }
  }

  function handleUnpublish(file: string) {
    if (confirmUnpublish === file) {
      onUnpublish(file);
      setConfirmUnpublish(null);
      if (unpublishTimerRef.current) clearTimeout(unpublishTimerRef.current);
    } else {
      setConfirmUnpublish(file);
      if (unpublishTimerRef.current) clearTimeout(unpublishTimerRef.current);
      unpublishTimerRef.current = setTimeout(() => setConfirmUnpublish((cur) => cur === file ? null : cur), 4000);
    }
  }

  const hasSession = rxTexts.join('\n').trim().length > 0;

  return (
    <Paper
      square
      elevation={0}
      sx={{
        display: 'flex',
        borderBottom: 1,
        borderColor: 'divider',
        maxHeight: 360,
        overflow: 'hidden',
      }}
    >
      {/* Left: journal list + generate button */}
      <Box
        sx={{
          width: 240,
          borderRight: 1,
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <Box sx={{ px: 1.5, py: 1, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>JOURNALS</Typography>
        </Box>

        <Box sx={{ flex: 1, overflowY: 'auto' }}>
          {journals.length === 0 ? (
            <Typography variant="body2" sx={{ color: 'text.secondary', p: 1.5, fontStyle: 'italic' }}>
              No saved journals.
            </Typography>
          ) : (
            <List dense disablePadding>
              {journals.map((j) => (
                <ListItem
                  key={j._file}
                  disablePadding
                  secondaryAction={
                    <Box sx={{ display: 'flex' }}>
                      {j.published ? (
                        <IconButton
                          size="small"
                          onClick={(e) => { e.stopPropagation(); handleUnpublish(j._file); }}
                          color={confirmUnpublish === j._file ? 'warning' : 'success'}
                          title={confirmUnpublish === j._file ? 'Click again to remove from /journal' : 'Published — click to remove from family journal'}
                          aria-label={confirmUnpublish === j._file ? 'Confirm remove from journal' : 'Remove from family journal'}
                        >
                          <UnpublishedIcon fontSize="small" />
                        </IconButton>
                      ) : (
                        <IconButton
                          size="small"
                          onClick={(e) => { e.stopPropagation(); handlePublish(j._file); }}
                          color={confirmPublish === j._file ? 'primary' : 'default'}
                          title={confirmPublish === j._file ? 'Click again to publish to /journal' : 'Publish to family journal'}
                          aria-label={confirmPublish === j._file ? 'Confirm publish' : 'Publish to family journal'}
                        >
                          <PublishIcon fontSize="small" />
                        </IconButton>
                      )}
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={(e) => { e.stopPropagation(); handleDelete(j._file); }}
                        color={confirmDelete === j._file ? 'error' : 'default'}
                        title={confirmDelete === j._file ? 'Click again to confirm' : 'Delete'}
                        aria-label={confirmDelete === j._file ? 'Confirm delete' : 'Delete journal'}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  }
                >
                  <ListItemButton
                    selected={selected?._file === j._file}
                    onClick={() => { setSelected(j); onDismissResult(); }}
                    sx={{ pr: 11 }}
                  >
                    <ListItemText
                      primary={j.title || '(untitled)'}
                      secondary={j.exported_at.slice(0, 10)}
                      slotProps={{
                        primary: {
                          variant: 'body2',
                          sx: {
                            overflow: 'hidden',
                            whiteSpace: 'nowrap',
                            textOverflow: 'ellipsis',
                            fontWeight: selected?._file === j._file ? 700 : 400,
                          },
                        },
                        secondary: { variant: 'caption' },
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          )}
        </Box>

        <Box sx={{ p: 1, borderTop: 1, borderColor: 'divider' }}>
          {journalError && (
            <Alert severity="error" sx={{ mb: 1, fontSize: '0.8125rem' }}>{journalError}</Alert>
          )}
          <Button
            fullWidth
            variant="contained"
            size="small"
            onClick={handleGenerate}
            disabled={generating || !hasSession}
            title={!hasSession ? 'No received messages to summarise' : ''}
          >
            {generating ? 'GENERATING…' : 'GENERATE FROM SESSION'}
          </Button>
        </Box>
      </Box>

      {/* Right: draft or selected journal detail */}
      <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
        {pendingResult ? (
          <Box>
            <Typography variant="h6" sx={{ mb: 2 }}>AI DRAFT — REVIEW AND SAVE</Typography>
            <TextField label="Title" fullWidth value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)} sx={{ mb: 2 }} />
            <TextField label="Summary" fullWidth multiline rows={5} value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)} sx={{ mb: 2 }} />
            {pendingResult.callsigns_locations.length > 0 && (
              <CallsignsTable rows={pendingResult.callsigns_locations} />
            )}
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button variant="contained" onClick={handleSave} disabled={!editTitle.trim()}>
                SAVE JOURNAL
              </Button>
              <Button variant="outlined" color="warning" onClick={onDismissResult}>
                DISCARD
              </Button>
            </Box>
          </Box>
        ) : selected ? (
          <Box>
            <Typography variant="caption" color="text.secondary">{selected.exported_at}</Typography>
            <Typography variant="h5" sx={{ mt: 0.5, mb: 2 }}>
              {selected.title || '(untitled)'}
            </Typography>
            {selected.callsigns_locations.length > 0 && (
              <CallsignsTable rows={selected.callsigns_locations} />
            )}
            <Typography variant="body1" sx={{ mb: 2 }}>{selected.summary}</Typography>
            {selected.transcript && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="body2">Session transcript</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box
                    component="pre"
                    sx={{ fontSize: '0.875rem', overflowX: 'auto', whiteSpace: 'pre-wrap', m: 0 }}
                  >
                    {selected.transcript}
                  </Box>
                </AccordionDetails>
              </Accordion>
            )}
          </Box>
        ) : (
          <Typography sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
            Select a journal or generate a new one.
          </Typography>
        )}
      </Box>
    </Paper>
  );
}
