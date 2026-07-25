import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Typography,
} from '@mui/material';
import type { IncidentEntry } from '../../types/ws';
import { incidentDensitySpec } from '../../neighborhood/density';
import { INCIDENT_CATEGORIES } from './IncidentDialog';

interface IncidentLogProps {
  incidents: IncidentEntry[];
  /** Admin-only log wipe. Omitted (not disabled) for everyone else, so a
   *  control that can't succeed never appears. */
  onClear?: () => void;
}

function categoryLabel(category: string): string {
  return INCIDENT_CATEGORIES.find((c) => c.value === category)?.label ?? category;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

/** Neighborhood incident feed: a category filter plus a newest-first list.
 *  Incidents already arrive newest-first from the server (see
 *  backend/persistence/incidents.py), so filtering never needs to re-sort.
 *
 *  Cards sit in an auto-fit grid whose size comes from how many are showing,
 *  so a quiet evening reads big and a busy one still fits on a screen instead
 *  of becoming a scroll. See neighborhood/density.ts. The grid flows in
 *  document order (row-major), so newest-first still reads newest-first.
 *
 *  The tier tracks the *filtered* count, not the raw one: narrowing to one
 *  category should give those cards the room the short list has earned. */
export function IncidentLog({ incidents, onClear }: IncidentLogProps) {
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all' ? incidents : incidents.filter((i) => i.category === filter);
  const density = incidentDensitySpec(filtered.length);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Incident log
        </Typography>
        {/* Clears the whole log, not the current filter — the label says so,
            and the confirm dialog spells out the journal-then-wipe. */}
        {onClear && incidents.length > 0 && (
          <Button size="small" color="error" onClick={onClear}>
            Clear incident log
          </Button>
        )}
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
        <Box
          role="list"
          aria-label="Incident reports"
          sx={{
            display: 'grid', gap: 1, justifyContent: 'start',
            // auto-fit packs as many columns as the viewport allows; the tier's
            // max keeps a single incident from becoming a billboard, and
            // min(…, 100%) stops a card overflowing a phone-width screen.
            gridTemplateColumns:
              `repeat(auto-fit, minmax(min(${density.minColumnPx}px, 100%), ${density.maxColumnPx}px))`,
          }}
        >
          {filtered.map((entry) => (
            <Paper
              key={entry.id}
              role="listitem"
              sx={{ p: density.padding, height: '100%', minWidth: 0, display: 'flex', flexDirection: 'column', gap: density.gap }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: density.gap * 2, flexWrap: 'wrap', minWidth: 0 }}>
                <Chip size="small" label={categoryLabel(entry.category)} sx={{ maxWidth: '100%' }} />
                <Typography variant="caption" color="text.secondary">
                  {formatTime(entry.ts)}
                </Typography>
              </Box>
              {/* overflowWrap keeps an unbroken string — a URL, a plate number —
                  inside a narrow compact-tier card. The description is never
                  truncated: an incident log that hides text is worse than one
                  that scrolls. */}
              <Typography variant={density.bodyVariant} sx={{ overflowWrap: 'anywhere' }}>
                {entry.description}
              </Typography>
              <Typography variant={density.detailVariant} color="text.secondary" sx={{ overflowWrap: 'anywhere', mt: 'auto' }}>
                Location: {entry.location} &middot; Reported by {entry.reporter}
              </Typography>
            </Paper>
          ))}
        </Box>
      )}
    </Box>
  );
}
