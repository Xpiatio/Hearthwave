import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import type { NCSSpotReportPayload, SpotHazard } from '../../types/ws';

interface SpotReportDialogProps {
  open: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: Omit<NCSSpotReportPayload, 'type'>) => void;
}

const HAZARDS: { value: SpotHazard; label: string }[] = [
  { value: 'tornado', label: 'Tornado' },
  { value: 'funnel_cloud', label: 'Funnel cloud' },
  { value: 'wall_cloud', label: 'Rotating wall cloud' },
  { value: 'hail', label: 'Hail' },
  { value: 'wind', label: 'Wind / damage' },
  { value: 'flooding', label: 'Flooding / rainfall' },
  { value: 'snow', label: 'Snow' },
  { value: 'other', label: 'Other' },
];

/** Local date-time string for a `datetime-local` input, defaulting to now. */
function nowLocalInput(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function SpotReportDialog({ open, error, onClose, onSubmit }: SpotReportDialogProps) {
  const [hazard, setHazard] = useState<SpotHazard>('tornado');
  const [location, setLocation] = useState('');
  const [observedAt, setObservedAt] = useState(nowLocalInput);
  const [detail, setDetail] = useState('');
  const [hailSize, setHailSize] = useState('');
  const [windMph, setWindMph] = useState('');
  const [windMethod, setWindMethod] = useState<'estimated' | 'measured'>('estimated');
  const [windDamage, setWindDamage] = useState('');
  const [rainAmount, setRainAmount] = useState('');
  const [rainDuration, setRainDuration] = useState('');
  const [snowAmount, setSnowAmount] = useState('');

  const num = (s: string): number | undefined => {
    const v = parseFloat(s);
    return Number.isFinite(v) ? v : undefined;
  };

  const valid = useMemo(() => {
    if (!location.trim()) return false;
    switch (hazard) {
      case 'hail':
        return (num(hailSize) ?? 0) >= 1.0;
      case 'wind':
        return (num(windMph) ?? 0) >= 40;
      case 'flooding':
        return (num(rainAmount) ?? 0) >= 1.0 || detail.trim().length > 0;
      case 'snow':
        return num(snowAmount) !== undefined || detail.trim().length > 0;
      case 'other':
        return detail.trim().length > 0;
      default:
        return true; // tornado / funnel / wall cloud
    }
  }, [hazard, location, hailSize, windMph, rainAmount, snowAmount, detail]);

  const handleSubmit = () => {
    if (!valid) return;
    const payload: Omit<NCSSpotReportPayload, 'type'> = {
      hazard,
      location: location.trim(),
      observed_at: observedAt ? new Date(observedAt).toISOString() : undefined,
    };
    if (detail.trim()) payload.detail = detail.trim();
    if (hazard === 'hail') payload.hail_size_in = num(hailSize);
    if (hazard === 'wind') {
      payload.wind_mph = num(windMph);
      payload.wind_method = windMethod;
      if (windDamage.trim()) payload.wind_damage = windDamage.trim();
    }
    if (hazard === 'flooding') {
      payload.rain_amount_in = num(rainAmount);
      payload.rain_duration_min = num(rainDuration);
    }
    if (hazard === 'snow') payload.snow_amount_in = num(snowAmount);
    onSubmit(payload);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>SKYWARN Spot Report</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}

          <FormControl size="small" fullWidth>
            <InputLabel id="spot-hazard-label">Hazard</InputLabel>
            <Select
              labelId="spot-hazard-label"
              label="Hazard"
              value={hazard}
              onChange={(e) => setHazard(e.target.value as SpotHazard)}
            >
              {HAZARDS.map((h) => (
                <MenuItem key={h.value} value={h.value}>{h.label}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {hazard === 'hail' && (
            <TextField
              size="small"
              type="number"
              label="Largest hailstone (inches)"
              value={hailSize}
              onChange={(e) => setHailSize(e.target.value)}
              helperText="≥ 1.00 in to meet reporting criteria"
              slotProps={{ htmlInput: { min: 1, step: 0.25 } }}
            />
          )}

          {hazard === 'wind' && (
            <>
              <TextField
                size="small"
                type="number"
                label="Wind speed (mph)"
                value={windMph}
                onChange={(e) => setWindMph(e.target.value)}
                helperText="≥ 40 mph to meet reporting criteria"
                slotProps={{ htmlInput: { min: 40, step: 1 } }}
              />
              <FormControl size="small" fullWidth>
                <InputLabel id="spot-wind-method-label">Method</InputLabel>
                <Select
                  labelId="spot-wind-method-label"
                  label="Method"
                  value={windMethod}
                  onChange={(e) => setWindMethod(e.target.value as 'estimated' | 'measured')}
                >
                  <MenuItem value="estimated">Estimated</MenuItem>
                  <MenuItem value="measured">Measured</MenuItem>
                </Select>
              </FormControl>
              <TextField
                size="small"
                label="Damage observed (optional)"
                value={windDamage}
                onChange={(e) => setWindDamage(e.target.value)}
                placeholder="e.g. large branches down"
              />
            </>
          )}

          {hazard === 'flooding' && (
            <>
              <TextField
                size="small"
                type="number"
                label="Rainfall (inches)"
                value={rainAmount}
                onChange={(e) => setRainAmount(e.target.value)}
                helperText="≥ 1 in within an hour, or describe flooding below"
                slotProps={{ htmlInput: { min: 0, step: 0.1 } }}
              />
              <TextField
                size="small"
                type="number"
                label="Over how many minutes (optional)"
                value={rainDuration}
                onChange={(e) => setRainDuration(e.target.value)}
                slotProps={{ htmlInput: { min: 0, step: 5 } }}
              />
            </>
          )}

          {hazard === 'snow' && (
            <TextField
              size="small"
              type="number"
              label="Snowfall (inches)"
              value={snowAmount}
              onChange={(e) => setSnowAmount(e.target.value)}
              slotProps={{ htmlInput: { min: 0, step: 0.5 } }}
            />
          )}

          <TextField
            size="small"
            label={hazard === 'other' ? 'What did you observe?' : 'Details (optional)'}
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            multiline
            minRows={2}
            required={hazard === 'other'}
          />

          <TextField
            size="small"
            label="Location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. 3 mi SW of Hastings, MI"
            required
          />

          <TextField
            size="small"
            type="datetime-local"
            label="Time observed"
            value={observedAt}
            onChange={(e) => setObservedAt(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          color="error"
          onClick={handleSubmit}
          disabled={!valid}
        >
          TRANSMIT REPORT
        </Button>
      </DialogActions>
    </Dialog>
  );
}
