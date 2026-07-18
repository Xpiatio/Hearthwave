import { useRef } from 'react';
import {
  Dialog,
  DialogActions,
  Button,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material';
import { useSwitchScan } from '../../hooks/useSwitchScan';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  body?: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  switchScan?: boolean;
  switchScanIntervalS?: number;
  onConfirm: () => void;
  onClose: () => void;
}

/**
 * Large stacked yes/no confirmation — AAC exit-confirm pattern
 * generalized all destructive actions (WCAG-friendly big targets,
 * explicit verb labels instead of OK/Cancel, optional switch scanning).
 */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  cancelLabel,
  destructive,
  switchScan,
  switchScanIntervalS,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const actionsRef = useRef<HTMLDivElement | null>(null);
  useSwitchScan(!!switchScan && open, (switchScanIntervalS ?? 1.5) * 1000, actionsRef);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{title}</DialogTitle>
      {body && (
        <DialogContent>
          <Typography>{body}</Typography>
        </DialogContent>
      )}
      <DialogActions ref={actionsRef} sx={{ flexDirection: 'column', gap: 1, p: 2 }}>
        <Button
          fullWidth
          variant="contained"
          color={destructive ? 'error' : 'primary'}
          data-scan="true"
          onClick={() => {
            onClose();
            onConfirm();
          }}
          sx={{ minHeight: 64, fontSize: '1.2rem' }}
        >
          ✅ {confirmLabel}
        </Button>
        <Button
          fullWidth
          variant="outlined"
          data-scan="true"
          onClick={onClose}
          sx={{ minHeight: 64, fontSize: '1.2rem' }}
        >
          ↩️ {cancelLabel ?? 'No, go back'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
