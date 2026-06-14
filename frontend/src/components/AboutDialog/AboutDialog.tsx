import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Link,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { Logo } from '../Logo/Logo';
import { useVersion } from '../../hooks/useVersion';

interface Props {
  open: boolean;
  onClose: () => void;
}

const GITHUB_URL = 'https://github.com/Xpiatio/Hearthwave';
const WEBSITE_URL = 'https://xpiatio.github.io/Hearthwave/';

export function AboutDialog({ open, onClose }: Props) {
  const version = useVersion();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        About Hearthwave
        <IconButton onClick={onClose} aria-label="Close about dialog" size="small" sx={{ color: 'inherit' }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, pt: 1, textAlign: 'center' }}>
          <Logo size={72} />
          <Typography variant="h6" sx={{ fontWeight: 800 }}>Hearthwave</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {version ? `v${version}` : 'version unavailable'}
          </Typography>
          <Typography variant="body2">Self-hosted GMRS hub for your household.</Typography>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Link href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub repository</Link>
          <Link href={WEBSITE_URL} target="_blank" rel="noopener noreferrer">Documentation &amp; website</Link>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
          Operates on GMRS under FCC Part 95 Subpart E. Every transmission is station-identified;
          you are responsible for holding a valid GMRS license and using your assigned call sign.
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 1 }}>
          A fork of GMRS-TTY. Speech-to-text by Whisper; text-to-speech by Piper.
        </Typography>
      </DialogContent>
    </Dialog>
  );
}
