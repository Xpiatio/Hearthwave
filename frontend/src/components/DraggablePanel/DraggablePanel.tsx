import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Box } from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';

interface Props {
  id: string;
  children: React.ReactNode;
}

export function DraggablePanel({ id, children }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });

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
        {...attributes}
        {...listeners}
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          py: 0.25,
          cursor: 'grab',
          bgcolor: 'action.hover',
          borderBottom: 1,
          borderColor: 'divider',
          color: 'text.secondary',
          '&:hover': { bgcolor: 'action.selected' },
          '&:active': { cursor: 'grabbing' },
          touchAction: 'none',
          userSelect: 'none',
        }}
      >
        <DragIndicatorIcon fontSize="small" sx={{ transform: 'rotate(90deg)' }} />
      </Box>
      {children}
    </Box>
  );
}
