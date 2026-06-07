import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Box, IconButton } from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';

interface Props {
  id: string;
  children: React.ReactNode;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
}

export function DraggablePanel({ id, children, onMoveUp, onMoveDown }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const showButtons = onMoveUp !== undefined || onMoveDown !== undefined;

  return (
    <Box
      ref={setNodeRef}
      sx={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        zIndex: isDragging ? 1000 : 'auto',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          py: 0.25,
          bgcolor: 'action.hover',
          borderBottom: 1,
          borderColor: 'divider',
          color: 'text.secondary',
          '&:hover': { bgcolor: 'action.selected' },
        }}
      >
        <Box
          {...attributes}
          {...listeners}
          role="button"
          tabIndex={0}
          aria-label={`Drag to reorder ${id} panel`}
          sx={{
            flex: 1,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            py: 0.25,
            cursor: 'grab',
            '&:active': { cursor: 'grabbing' },
            touchAction: 'none',
            userSelect: 'none',
          }}
        >
          <DragIndicatorIcon fontSize="small" sx={{ transform: 'rotate(90deg)' }} />
        </Box>
        {showButtons && (
          <Box sx={{ display: 'flex', gap: 0.25, pr: 0.5 }}>
            <IconButton
              size="small"
              onClick={onMoveUp}
              disabled={onMoveUp === undefined}
              aria-label={`Move ${id} panel up`}
            >
              <KeyboardArrowUpIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={onMoveDown}
              disabled={onMoveDown === undefined}
              aria-label={`Move ${id} panel down`}
            >
              <KeyboardArrowDownIcon fontSize="small" />
            </IconButton>
          </Box>
        )}
      </Box>
      {children}
    </Box>
  );
}
