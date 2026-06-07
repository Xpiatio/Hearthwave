import React from 'react';
import { Box, Typography } from '@mui/material';

interface PanelHeaderProps {
  title: string;
  gradient: string;
  icon?: React.ReactNode;
}

export function PanelHeader({ title, gradient, icon }: PanelHeaderProps) {
  return (
    <Box
      sx={{
        background: gradient,
        px: 2,
        py: 1,
        display: 'flex',
        alignItems: 'center',
        gap: 1,
      }}
    >
      {icon}
      <Typography
        variant="subtitle2"
        sx={{ fontWeight: 700, textTransform: 'uppercase', color: '#F9FAFB' }}
      >
        {title}
      </Typography>
    </Box>
  );
}
