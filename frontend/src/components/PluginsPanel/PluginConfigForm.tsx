import { Box, TextField, Switch, FormControlLabel, MenuItem } from '@mui/material';
import type { PluginConfigField } from '../../types/ws';

interface Props {
  schema: PluginConfigField[];
  /** Current values keyed by field key (falls back to each field's default). */
  values: Record<string, unknown>;
  disabled?: boolean;
  onChange: (key: string, value: unknown) => void;
}

/**
 * Renders a plugin's declarative config schema into MUI form fields. Pure and
 * generic — no plugin-supplied code runs in the browser. Supports bool / text /
 * number / select field types.
 */
export function PluginConfigForm({ schema, values, disabled, onChange }: Props) {
  if (schema.length === 0) return null;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1.5 }}>
      {schema.map((field) => {
        const value = values[field.key] ?? field.default;

        if (field.type === 'bool') {
          return (
            <FormControlLabel
              key={field.key}
              control={
                <Switch
                  size="small"
                  checked={Boolean(value)}
                  disabled={disabled}
                  onChange={(e) => onChange(field.key, e.target.checked)}
                />
              }
              label={field.label}
            />
          );
        }

        if (field.type === 'select') {
          return (
            <TextField
              key={field.key}
              select
              size="small"
              fullWidth
              label={field.label}
              value={String(value ?? '')}
              disabled={disabled}
              helperText={field.help || undefined}
              onChange={(e) => onChange(field.key, e.target.value)}
            >
              {field.options.map(([optValue, optLabel]) => (
                <MenuItem key={optValue} value={optValue}>{optLabel}</MenuItem>
              ))}
            </TextField>
          );
        }

        if (field.type === 'number') {
          return (
            <TextField
              key={field.key}
              type="number"
              size="small"
              fullWidth
              label={field.label}
              value={value as number}
              disabled={disabled}
              helperText={field.help || undefined}
              slotProps={{ htmlInput: { min: field.minimum ?? undefined, max: field.maximum ?? undefined } }}
              onChange={(e) => onChange(field.key, e.target.value === '' ? '' : Number(e.target.value))}
            />
          );
        }

        return (
          <TextField
            key={field.key}
            size="small"
            fullWidth
            label={field.label}
            value={String(value ?? '')}
            disabled={disabled}
            helperText={field.help || undefined}
            onChange={(e) => onChange(field.key, e.target.value)}
          />
        );
      })}
    </Box>
  );
}
