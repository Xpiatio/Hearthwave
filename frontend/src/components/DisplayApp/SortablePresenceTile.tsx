import { Box } from '@mui/material';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { PresenceTile, type PresenceTileProps } from './PresenceTile';

/** A presence tile the operator can long-press and drag to re-sort.
 *
 *  The drag listeners sit on the wrapper rather than the tile so the tile's
 *  own "Mark OK" tap target keeps working — dnd-kit's press-delay sensor
 *  swallows the pointer only once a drag actually starts.
 */
export function SortablePresenceTile(props: PresenceTileProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: props.entry.user_id,
  });

  return (
    <Box
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      // After the spread: dnd-kit defaults these tiles to role="button", but
      // they live in a role="list" grid and the tap target is the tile itself.
      role="listitem"
      sx={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        zIndex: isDragging ? 1 : undefined,
        touchAction: 'manipulation',
        cursor: 'grab',
      }}
    >
      <PresenceTile {...props} />
    </Box>
  );
}
