import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import EditIcon from '@mui/icons-material/Edit';
import CloseIcon from '@mui/icons-material/Close';
import CancelIcon from '@mui/icons-material/Cancel';
import AddIcon from '@mui/icons-material/Add';
import type { AACButton, AACCategory, AACGrid } from '../../types/aac';
import { AAC_MAX_CATEGORIES } from '../../types/aac';
import type { ChatEntry } from '../ChatDisplay/ChatDisplay';
import type { UserProfile } from '../../types/ws';
import { newId, resolveTokens } from './defaultGrid';
import { SentenceStrip } from './SentenceStrip';
import { IncomingStrip } from './IncomingStrip';
import { ButtonGrid } from './ButtonGrid';
import { ButtonEditorDialog } from './ButtonEditorDialog';
import { ConfirmDialog } from '../ConfirmDialog';
import { useSwitchScan } from '../../hooks/useSwitchScan';

export interface AACAppProps {
  profile: UserProfile;
  effectiveCallsign: string;
  connected: boolean;
  transmitting: boolean;
  listenOnly: boolean;
  messages: ChatEntry[];
  grid: AACGrid;
  onSend: (text: string, targetCall: string, targetName: string) => void;
  onTxAbort: () => void;
  onSaveGrid: (grid: AACGrid) => void;
  onExitAac: () => void;
  switchScan: boolean;
  switchScanIntervalS: number;
}

export function AACApp({
  profile,
  effectiveCallsign,
  connected,
  transmitting,
  listenOnly,
  messages,
  grid,
  onSend,
  onTxAbort,
  onSaveGrid,
  onExitAac,
  switchScan,
  switchScanIntervalS,
}: AACAppProps) {
  const [chunks, setChunks] = useState<string[]>([]);
  const [activeCatId, setActiveCatId] = useState<string>(grid.categories[0]?.id ?? '');
  const [editMode, setEditMode] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorButton, setEditorButton] = useState<AACButton | null>(null);
  const [exitConfirmOpen, setExitConfirmOpen] = useState(false);
  const [catEditorOpen, setCatEditorOpen] = useState(false);
  const [catEditorTarget, setCatEditorTarget] = useState<AACCategory | null>(null);
  const [catDraftName, setCatDraftName] = useState('');
  const [catDraftEmoji, setCatDraftEmoji] = useState('');
  const [catDeleteConfirmOpen, setCatDeleteConfirmOpen] = useState(false);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const scanActive =
    switchScan && !editMode && !editorOpen && !catEditorOpen && !exitConfirmOpen && !catDeleteConfirmOpen;
  useSwitchScan(scanActive, switchScanIntervalS * 1000, rootRef);

  // Keep the active tab valid when the grid changes (edits, server refresh).
  useEffect(() => {
    if (!grid.categories.some((c) => c.id === activeCatId)) {
      setActiveCatId(grid.categories[0]?.id ?? '');
    }
  }, [grid, activeCatId]);

  const activeCategory = grid.categories.find((c) => c.id === activeCatId) ?? grid.categories[0];
  const canSend = chunks.length > 0 && connected && !listenOnly && !editMode;

  function handlePress(button: AACButton) {
    if (editMode) {
      setEditorButton(button);
      setEditorOpen(true);
    } else {
      setChunks((prev) => [...prev, button.text]);
    }
  }

  function handleSendClick() {
    if (!canSend) return;
    const text = resolveTokens(chunks.join(' '), profile.operator_name, effectiveCallsign);
    if (!text) return;
    onSend(text, '', '');
    setChunks([]);
  }

  function mutateCategory(catId: string, mutate: (c: AACCategory) => AACCategory | null) {
    const categories = grid.categories
      .map((c) => (c.id === catId ? mutate(c) : c))
      .filter((c): c is AACCategory => c !== null);
    onSaveGrid({ ...grid, categories });
  }

  function handleSaveButton(button: AACButton) {
    if (!activeCategory) return;
    mutateCategory(activeCategory.id, (c) => {
      const exists = c.buttons.some((b) => b.id === button.id);
      return {
        ...c,
        buttons: exists
          ? c.buttons.map((b) => (b.id === button.id ? button : b))
          : [...c.buttons, button],
      };
    });
  }

  function handleDeleteButton(id: string) {
    if (!activeCategory) return;
    mutateCategory(activeCategory.id, (c) => ({
      ...c,
      buttons: c.buttons.filter((b) => b.id !== id),
    }));
  }

  function openCategoryEditor(target: AACCategory | null) {
    setCatEditorTarget(target);
    setCatDraftName(target?.name ?? '');
    setCatDraftEmoji(target?.emoji ?? '📁');
    setCatEditorOpen(true);
  }

  function handleSaveCategory() {
    const name = catDraftName.trim();
    if (!name) return;
    const emoji = catDraftEmoji.trim() || '📁';
    if (catEditorTarget) {
      mutateCategory(catEditorTarget.id, (c) => ({ ...c, name, emoji }));
    } else {
      const cat: AACCategory = { id: newId('c'), name, emoji, buttons: [] };
      onSaveGrid({ ...grid, categories: [...grid.categories, cat] });
      setActiveCatId(cat.id);
    }
    setCatEditorOpen(false);
  }

  function requestDeleteCategory() {
    if (!catEditorTarget || grid.categories.length <= 1) return;
    setCatDeleteConfirmOpen(true);
  }

  function handleDeleteCategory() {
    if (!catEditorTarget) return;
    mutateCategory(catEditorTarget.id, () => null);
    setCatEditorOpen(false);
  }

  return (
    <Box ref={rootRef} sx={{ height: '100vh', minHeight: '100dvh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1.5,
          py: 0.75,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Typography variant="h6" component="h1" sx={{ flex: 1 }}>
          {profile.avatar_emoji} {profile.operator_name || profile.display_name}
          {effectiveCallsign ? ` · ${effectiveCallsign}` : ''}
        </Typography>
        {!connected && <Chip color="error" label="Disconnected" />}
        {listenOnly && <Chip color="warning" label="Listen only" />}
        <Tooltip title={editMode ? 'Done editing' : 'Edit buttons'}>
          <IconButton
            onClick={() => setEditMode((v) => !v)}
            aria-label={editMode ? 'Done editing buttons' : 'Edit buttons'}
            aria-pressed={editMode}
            color={editMode ? 'primary' : 'default'}
          >
            <EditIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="Exit AAC mode">
          <IconButton onClick={() => setExitConfirmOpen(true)} aria-label="Exit AAC mode">
            <CloseIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <IncomingStrip messages={messages} />
      <SentenceStrip
        chunks={chunks}
        onBackspace={() => setChunks((prev) => prev.slice(0, -1))}
        onClear={() => setChunks([])}
      />

      {/* Category tabs */}
      <Box sx={{ display: 'flex', alignItems: 'center', borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeCategory?.id ?? false}
          onChange={(_e, v) => setActiveCatId(v)}
          variant="scrollable"
          scrollButtons="auto"
          aria-label="Message categories"
          sx={{ flex: 1 }}
        >
          {grid.categories.map((c) => (
            <Tab
              key={c.id}
              value={c.id}
              label={
                <span>
                  <span aria-hidden="true">{c.emoji} </span>
                  {c.name}
                </span>
              }
              data-scan="true"
              sx={{ fontSize: '1rem', minHeight: 56 }}
            />
          ))}
        </Tabs>
        {editMode && (
          <>
            {activeCategory && (
              <Button size="small" onClick={() => openCategoryEditor(activeCategory)} aria-label="Edit category">
                <EditIcon fontSize="small" sx={{ mr: 0.5 }} /> Category
              </Button>
            )}
            {grid.categories.length < AAC_MAX_CATEGORIES && (
              <IconButton onClick={() => openCategoryEditor(null)} aria-label="Add category">
                <AddIcon />
              </IconButton>
            )}
          </>
        )}
      </Box>

      {/* Button grid */}
      {activeCategory ? (
        <ButtonGrid
          category={activeCategory}
          editMode={editMode}
          onPress={handlePress}
          onAdd={() => {
            setEditorButton(null);
            setEditorOpen(true);
          }}
        />
      ) : (
        <Box sx={{ flex: 1, p: 2 }}>
          <Typography color="text.secondary">No categories. Use edit mode to add one.</Typography>
        </Box>
      )}

      {/* Send bar */}
      <Box sx={{ display: 'flex', gap: 1, p: 1, borderTop: 1, borderColor: 'divider' }}>
        {transmitting ? (
          <>
            <Alert severity="info" role="alert" aria-live="assertive" sx={{ flex: 1 }}>
              Transmitting…
            </Alert>
            <Button
              variant="contained"
              color="error"
              onClick={onTxAbort}
              aria-label="Abort transmission"
              data-scan="true"
              startIcon={<CancelIcon />}
              sx={{ minHeight: 72, px: 3 }}
            >
              ABORT
            </Button>
          </>
        ) : (
          <Button
            fullWidth
            variant="contained"
            color="primary"
            onClick={handleSendClick}
            disabled={!canSend}
            aria-label="Send message over radio"
            data-scan="true"
            startIcon={<SendIcon sx={{ fontSize: '2rem' }} />}
            sx={{ minHeight: 72, fontSize: '1.4rem' }}
          >
            {listenOnly ? 'LISTEN-ONLY MODE — SENDING DISABLED' : editMode ? 'EDITING — TAP A BUTTON TO CHANGE IT' : 'SEND'}
          </Button>
        )}
      </Box>

      <ButtonEditorDialog
        open={editorOpen}
        button={editorButton}
        onSave={handleSaveButton}
        onDelete={handleDeleteButton}
        onClose={() => setEditorOpen(false)}
      />

      {/* Category editor */}
      <Dialog open={catEditorOpen} onClose={() => setCatEditorOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>{catEditorTarget ? 'Edit Category' : 'Add Category'}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <TextField
              label="Emoji"
              value={catDraftEmoji}
              onChange={(e) => setCatDraftEmoji(e.target.value)}
              slotProps={{ htmlInput: { maxLength: 8, style: { fontSize: '1.5rem' } } }}
            />
            <TextField
              label="Name"
              value={catDraftName}
              onChange={(e) => setCatDraftName(e.target.value)}
              required
              error={!catDraftName.trim()}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          {catEditorTarget && grid.categories.length > 1 && (
            <Button color="error" onClick={requestDeleteCategory}>
              DELETE
            </Button>
          )}
          <Box sx={{ flex: 1 }} />
          <Button onClick={() => setCatEditorOpen(false)}>CANCEL</Button>
          <Button variant="contained" onClick={handleSaveCategory} disabled={!catDraftName.trim()}>
            SAVE
          </Button>
        </DialogActions>
      </Dialog>

      {/* Exit confirmation — only path back to normal UI */}
      <ConfirmDialog
        open={exitConfirmOpen}
        title="Exit AAC mode?"
        body="This switches back to the standard Hearthwave screen."
        confirmLabel="Yes, exit"
        cancelLabel="No, stay here"
        switchScan={switchScan}
        switchScanIntervalS={switchScanIntervalS}
        onConfirm={onExitAac}
        onClose={() => setExitConfirmOpen(false)}
      />

      {/* Category delete confirmation */}
      <ConfirmDialog
        open={catDeleteConfirmOpen}
        title="Delete this category?"
        body={catEditorTarget ? `"${catEditorTarget.name}" and all its buttons will be removed.` : ''}
        confirmLabel="Yes, delete it"
        destructive
        switchScan={switchScan}
        switchScanIntervalS={switchScanIntervalS}
        onConfirm={handleDeleteCategory}
        onClose={() => setCatDeleteConfirmOpen(false)}
      />
    </Box>
  );
}
