import { useState, useEffect, useRef, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  IconButton,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  TextField,
  Box,
  Chip,
  Tooltip,
  CircularProgress,
  Typography,
  Stack,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import type { Contact, FccLookupResultMsg } from '../../types/ws';

interface Props {
  open: boolean;
  onClose: () => void;
  contacts: Contact[];
  prefilledCallsign?: string;
  fccLookupResult: FccLookupResultMsg | null;
  verifyAllComplete: boolean;
  onSend: (payload: unknown) => void;
  onVerifyAllDismiss: () => void;
}

interface FormData {
  callsign: string;
  name: string;
  location: string;
  gmrs_callsign: string;
  ham_callsign: string;
}

const EMPTY_FORM: FormData = {
  callsign: '',
  name: '',
  location: '',
  gmrs_callsign: '',
  ham_callsign: '',
};

function suffixKey(callsign: string): string {
  const m = callsign.match(/^[A-Z]+(\d+)([A-Z]+)$/i);
  if (m) return m[2].toUpperCase() + m[1].padStart(6, '0');
  return callsign.toUpperCase();
}

function contactsToCsv(contacts: Contact[]): string {
  const header = 'callsign,name,location,gmrs_callsign,ham_callsign,verified';
  const rows = contacts.map((c) =>
    [
      c.callsign,
      c.name ?? '',
      c.location ?? '',
      c.gmrs_callsign ?? '',
      c.ham_callsign ?? '',
      c.verified ? 'true' : 'false',
    ]
      .map((v) => `"${String(v).replace(/"/g, '""')}"`)
      .join(',')
  );
  return [header, ...rows].join('\n');
}

function parseCsv(text: string): FormData[] {
  const lines = text.trim().split('\n');
  if (lines.length < 2) return [];
  const header = lines[0].split(',').map((h) => h.trim().toLowerCase().replace(/^"|"$/g, ''));
  const idx = (name: string) => header.indexOf(name);
  return lines.slice(1).map((line) => {
    const cols = line.match(/("(?:[^"]|"")*"|[^,]*)/g)?.map((v) => v.replace(/^"|"$/g, '').replace(/""/g, '"')) ?? [];
    return {
      callsign: cols[idx('callsign')] ?? '',
      name: cols[idx('name')] ?? '',
      location: cols[idx('location')] ?? '',
      gmrs_callsign: cols[idx('gmrs_callsign')] ?? '',
      ham_callsign: cols[idx('ham_callsign')] ?? '',
    };
  }).filter((r) => r.callsign.trim());
}

function downloadText(text: string, filename: string, mime: string) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ContactsDialog({
  open,
  onClose,
  contacts,
  prefilledCallsign,
  fccLookupResult,
  verifyAllComplete,
  onSend,
  onVerifyAllDismiss,
}: Props) {
  const [sortBySuffix, setSortBySuffix] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingCallsign, setEditingCallsign] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [fccLoading, setFccLoading] = useState(false);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  // Open add dialog pre-filled when prefilledCallsign changes
  useEffect(() => {
    if (open && prefilledCallsign) {
      setForm({ ...EMPTY_FORM, callsign: prefilledCallsign });
      setEditingCallsign(null);
      setEditOpen(true);
    }
  }, [open, prefilledCallsign]);

  // Auto-fill form from FCC lookup result
  useEffect(() => {
    if (!fccLookupResult || !editOpen) return;
    if (fccLookupResult.callsign.toUpperCase() !== form.callsign.toUpperCase()) return;
    setForm((prev) => ({
      ...prev,
      name: fccLookupResult.license_name || prev.name,
      location: fccLookupResult.license_city || prev.location,
      gmrs_callsign: fccLookupResult.gmrs_callsign || prev.gmrs_callsign,
      ham_callsign: fccLookupResult.ham_callsign || prev.ham_callsign,
    }));
    setFccLoading(false);
  }, [fccLookupResult, editOpen, form.callsign]);

  // Clear verifyLoading when complete
  useEffect(() => {
    if (verifyAllComplete) setVerifyLoading(false);
  }, [verifyAllComplete]);

  const sorted = useMemo(
    () => sortBySuffix
      ? [...contacts].sort((a, b) => suffixKey(a.callsign).localeCompare(suffixKey(b.callsign)))
      : [...contacts].sort((a, b) => a.callsign.localeCompare(b.callsign)),
    [contacts, sortBySuffix]
  );

  function openAdd() {
    setForm(EMPTY_FORM);
    setEditingCallsign(null);
    setFccLoading(false);
    setEditOpen(true);
  }

  function openEdit(c: Contact) {
    setForm({
      callsign: c.callsign,
      name: c.name ?? '',
      location: c.location ?? '',
      gmrs_callsign: c.gmrs_callsign ?? '',
      ham_callsign: c.ham_callsign ?? '',
    });
    setEditingCallsign(c.callsign);
    setFccLoading(false);
    setEditOpen(true);
  }

  function handleSaveContact() {
    const callsign = form.callsign.trim().toUpperCase();
    if (!callsign) return;
    onSend({
      type: 'add_contact',
      callsign,
      name: form.name.trim(),
      location: form.location.trim(),
      gmrs_callsign: form.gmrs_callsign.trim().toUpperCase(),
      ham_callsign: form.ham_callsign.trim().toUpperCase(),
    });
    setEditOpen(false);
  }

  function handleDelete(callsign: string) {
    onSend({ type: 'delete_contact', callsign });
  }

  function handleFccLookup() {
    const cs = form.callsign.trim().toUpperCase();
    if (!cs) return;
    setFccLoading(true);
    onSend({ type: 'fcc_lookup', callsign: cs, name: form.name.trim() });
  }

  function handleVerifyAll() {
    setVerifyLoading(true);
    onVerifyAllDismiss();
    onSend({ type: 'verify_all' });
  }

  function handleExportJson() {
    downloadText(
      JSON.stringify(contacts, null, 2),
      'contacts.json',
      'application/json'
    );
  }

  function handleExportCsv() {
    downloadText(contactsToCsv(contacts), 'contacts.csv', 'text/csv');
  }

  function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      let records: FormData[] = [];
      if (file.name.endsWith('.csv')) {
        records = parseCsv(text);
      } else {
        try {
          const parsed = JSON.parse(text);
          records = Array.isArray(parsed) ? parsed : [];
        } catch {
          return;
        }
      }
      for (const r of records) {
        if (r.callsign?.trim()) {
          onSend({
            type: 'add_contact',
            callsign: r.callsign.trim().toUpperCase(),
            name: r.name ?? '',
            location: r.location ?? '',
            gmrs_callsign: r.gmrs_callsign ?? '',
            ham_callsign: r.ham_callsign ?? '',
          });
        }
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth
        slotProps={{ paper: { sx: { height: '80vh' } } }}>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            Contacts
            <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
              ({contacts.length})
            </Typography>
            {verifyAllComplete && (
              <Chip label="Verify complete" color="success" size="small" onDelete={onVerifyAllDismiss} />
            )}
          </Box>
        </DialogTitle>

        <DialogContent sx={{ p: 0, display: 'flex', flexDirection: 'column' }}>
          {/* Toolbar */}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', px: 2, py: 1, borderBottom: 1, borderColor: 'divider' }}>
            <Button size="small" variant="contained" onClick={openAdd}>
              Add Contact
            </Button>
            <Button
              size="small"
              variant={sortBySuffix ? 'contained' : 'outlined'}
              onClick={() => setSortBySuffix((v) => !v)}
            >
              Sort by Suffix
            </Button>
            <Button
              size="small"
              variant="outlined"
              onClick={handleVerifyAll}
              disabled={verifyLoading || contacts.length === 0}
              startIcon={verifyLoading ? <CircularProgress size={14} /> : undefined}
            >
              Verify All
            </Button>
            <Box sx={{ flex: 1 }} />
            <input
              ref={importRef}
              type="file"
              accept=".json,.csv"
              style={{ display: 'none' }}
              onChange={handleImport}
            />
            <Button size="small" variant="outlined" onClick={() => importRef.current?.click()}>
              Import
            </Button>
            <Button size="small" variant="outlined" onClick={handleExportJson}>
              Export JSON
            </Button>
            <Button size="small" variant="outlined" onClick={handleExportCsv}>
              Export CSV
            </Button>
          </Box>

          {/* Table */}
          <TableContainer sx={{ flex: 1, overflow: 'auto' }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Callsign</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Location</TableCell>
                  <TableCell>GMRS</TableCell>
                  <TableCell>HAM</TableCell>
                  <TableCell align="center">Verified</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sorted.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                      No contacts yet. Add one above.
                    </TableCell>
                  </TableRow>
                )}
                {sorted.map((c) => (
                  <TableRow key={c.callsign} hover>
                    <TableCell sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
                      {c.callsign}
                    </TableCell>
                    <TableCell>{c.name ?? ''}</TableCell>
                    <TableCell>{c.location ?? ''}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace' }}>{c.gmrs_callsign ?? ''}</TableCell>
                    <TableCell sx={{ fontFamily: 'monospace' }}>{c.ham_callsign ?? ''}</TableCell>
                    <TableCell align="center">
                      {c.verified && (
                        <Tooltip title={c.verified_at ? `Verified ${c.verified_at}` : 'Verified'}>
                          <CheckCircleIcon color="success" fontSize="small" />
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      <IconButton size="small" onClick={() => openEdit(c)} aria-label={`Edit ${c.callsign}`}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleDelete(c.callsign)}
                        aria-label={`Delete ${c.callsign}`}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Add / Edit dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingCallsign ? 'Edit Contact' : 'Add Contact'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="Callsign *"
              value={form.callsign}
              onChange={(e) => setForm((p) => ({ ...p, callsign: e.target.value.toUpperCase() }))}
              disabled={editingCallsign !== null}
              slotProps={{ htmlInput: { style: { fontFamily: 'monospace' } } }}
              fullWidth
            />
            <TextField
              label="Name"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              fullWidth
            />
            <TextField
              label="Location"
              value={form.location}
              onChange={(e) => setForm((p) => ({ ...p, location: e.target.value }))}
              fullWidth
            />
            <TextField
              label="GMRS Callsign"
              value={form.gmrs_callsign}
              onChange={(e) => setForm((p) => ({ ...p, gmrs_callsign: e.target.value.toUpperCase() }))}
              slotProps={{ htmlInput: { style: { fontFamily: 'monospace' } } }}
              fullWidth
            />
            <TextField
              label="HAM Callsign"
              value={form.ham_callsign}
              onChange={(e) => setForm((p) => ({ ...p, ham_callsign: e.target.value.toUpperCase() }))}
              slotProps={{ htmlInput: { style: { fontFamily: 'monospace' } } }}
              fullWidth
            />
            <Button
              variant="outlined"
              onClick={handleFccLookup}
              disabled={!form.callsign.trim() || fccLoading}
              startIcon={fccLoading ? <CircularProgress size={16} /> : undefined}
            >
              FCC Look Up
            </Button>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSaveContact}
            disabled={!form.callsign.trim()}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
