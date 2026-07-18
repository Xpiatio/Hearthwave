import { useRef, useState } from 'react';
import { Box, Button } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import type { AACButton, AACCategory } from '../../types/aac';
import { AAC_MAX_BUTTONS_PER_CATEGORY } from '../../types/aac';
import { AACGridButton } from './AACGridButton';

interface Props {
  category: AACCategory;
  editMode: boolean;
  onPress: (button: AACButton) => void;
  onAdd: () => void;
}

export function ButtonGrid({ category, editMode, onPress, onAdd }: Props) {
  // Roving tabindex: one word button is tabbable; arrows move focus.
  const [focusIdx, setFocusIdx] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const count = category.buttons.length;
  const effectiveFocusIdx = Math.min(focusIdx, Math.max(0, count - 1));
  function handleKeyDown(e: React.KeyboardEvent, idx: number) {
    let next = idx;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (idx + 1) % count;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (idx - 1 + count) % count;
    else return;
    e.preventDefault();
    setFocusIdx(next);
    refs.current[next]?.focus();
  }
  return (
    <Box
      role="group"
      aria-label={`${category.name} buttons`}
      sx={{
        flex: 1,
        overflowY: 'auto',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
        gap: 1,
        p: 1,
        alignContent: 'start',
      }}
    >
      {category.buttons.map((b, i) => (
        <AACGridButton
          key={b.id}
          button={b}
          editMode={editMode}
          onPress={onPress}
          buttonRef={(el) => { refs.current[i] = el; }}
          tabIndex={i === effectiveFocusIdx ? 0 : -1}
          onKeyDown={(e) => handleKeyDown(e, i)}
          onFocus={() => setFocusIdx(i)}
        />
      ))}
      {editMode && category.buttons.length < AAC_MAX_BUTTONS_PER_CATEGORY && (
        <Button
          variant="outlined"
          onClick={onAdd}
          aria-label="Add new button"
          sx={{ minHeight: 88, borderStyle: 'dashed', flexDirection: 'column', gap: 0.5 }}
        >
          <AddIcon sx={{ fontSize: '2rem' }} />
          Add
        </Button>
      )}
    </Box>
  );
}
