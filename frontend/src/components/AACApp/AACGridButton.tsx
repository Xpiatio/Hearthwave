import { Button, Typography } from '@mui/material';
import type { AACButton } from '../../types/aac';

interface Props {
  button: AACButton;
  editMode: boolean;
  onPress: (button: AACButton) => void;
}

export function AACGridButton({ button, editMode, onPress }: Props) {
  return (
    <Button
      variant="outlined"
      onClick={() => onPress(button)}
      aria-label={editMode ? `Edit button: ${button.label}` : button.label}
      sx={{
        minHeight: 88,
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
        p: 1,
        textTransform: 'none',
        borderWidth: editMode ? 2 : 1,
        borderStyle: editMode ? 'dashed' : 'solid',
      }}
    >
      <Typography component="span" aria-hidden="true" sx={{ fontSize: '2.25rem', lineHeight: 1 }}>
        {button.emoji}
      </Typography>
      <Typography component="span" sx={{ fontSize: '1rem', fontWeight: 600, wordBreak: 'break-word' }}>
        {button.label}
      </Typography>
    </Button>
  );
}
