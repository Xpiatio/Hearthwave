import { useState } from 'react';
import {
  Box,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Typography,
} from '@mui/material';
import type { IncidentEntry } from '../../types/ws';
import { INCIDENT_CATEGORIES } from './IncidentDialog';

interface IncidentLogProps {
  incidents: IncidentEntry[];
}

function categoryLabel(category: string): string {
  return INCIDENT_CATEGORIES.find((c) => c.value === category)?.label ?? category;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

/** Neighborhood incident feed: a category filter plus a newest-first list.
 *  Incidents already arrive newest-first from the server (see
 *  backend/persistence/incidents.py), so filtering never needs to re-sort. */
export function IncidentLog({ incidents }: IncidentLogProps) {
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all' ? incidents : incidents.filter((i) => i.category === filter);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Incident log
        </Typography>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel id="incident-filter-label">Filter by category</InputLabel>
          <Select
            labelId="incident-filter-label"
            label="Filter by category"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <MenuItem value="all">All</MenuItem>
            {INCIDENT_CATEGORIES.map((c) => (
              <MenuItem key={c.value} value={c.value}>{c.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {filtered.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No incidents reported.
        </Typography>
      ) : (
        <Box role="list" aria-label="Incident reports" sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {filtered.map((entry) => (
            <Paper key={entry.id} role="listitem" sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip size="small" label={categoryLabel(entry.category)} />
                <Typography variant="caption" color="text.secondary">
                  {formatTime(entry.ts)}
                </Typography>
              </Box>
              <Typography variant="body2">{entry.description}</Typography>
              <Typography variant="body2" color="text.secondary">
                Location: {entry.location} &middot; Reported by {entry.reporter}
              </Typography>
            </Paper>
          ))}
        </Box>
      )}
    </Box>
  );
}
