import { render as rtlRender, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { RadioCheckinForm } from '../RadioCheckinForm';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

const CONTACTS = [
  { callsign: 'WRAB123', name: 'Maria', location: 'Maple St' },
  { callsign: 'WRAC456', name: 'Diego', location: 'Oak St' },
];

describe('RadioCheckinForm', () => {
  it('disables the check-in button until callsign and name are filled', async () => {
    const user = userEvent.setup();
    render(<RadioCheckinForm contacts={[]} onCheckin={vi.fn()} />);
    const button = screen.getByRole('button', { name: /check in station/i });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/callsign/i), 'WRAB123');
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/^name/i), 'Maria');
    expect(button).toBeEnabled();
  });

  it('does not enable on whitespace alone', async () => {
    const user = userEvent.setup();
    render(<RadioCheckinForm contacts={[]} onCheckin={vi.fn()} />);
    await user.type(screen.getByLabelText(/callsign/i), '  ');
    await user.type(screen.getByLabelText(/^name/i), '  ');
    expect(screen.getByRole('button', { name: /check in station/i })).toBeDisabled();
  });

  it('fills the fields from a picked contact', async () => {
    const user = userEvent.setup();
    render(<RadioCheckinForm contacts={CONTACTS} onCheckin={vi.fn()} />);
    await user.click(screen.getByLabelText(/pick a neighbor/i));
    await user.click(screen.getByRole('option', { name: /WRAB123 — Maria/ }));
    expect(screen.getByLabelText(/callsign/i)).toHaveValue('WRAB123');
    expect(screen.getByLabelText(/^name/i)).toHaveValue('Maria');
    expect(screen.getByLabelText(/location/i)).toHaveValue('Maple St');
  });

  it('offers "save to contacts" only for a callsign the book does not have', async () => {
    const user = userEvent.setup();
    render(<RadioCheckinForm contacts={CONTACTS} onCheckin={vi.fn()} />);
    await user.type(screen.getByLabelText(/callsign/i), 'wrab123');
    expect(screen.queryByLabelText(/save to contacts/i)).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText(/callsign/i));
    await user.type(screen.getByLabelText(/callsign/i), 'WRAZ999');
    expect(screen.getByLabelText(/save to contacts/i)).toBeInTheDocument();
  });

  it('submits trimmed, upper-cased values and clears the form', async () => {
    const user = userEvent.setup();
    const onCheckin = vi.fn();
    render(<RadioCheckinForm contacts={CONTACTS} onCheckin={onCheckin} />);
    await user.type(screen.getByLabelText(/callsign/i), ' wraz999 ');
    await user.type(screen.getByLabelText(/^name/i), ' Sam ');
    await user.type(screen.getByLabelText(/location/i), ' Elm St ');
    await user.click(screen.getByLabelText(/save to contacts/i));
    await user.click(screen.getByRole('button', { name: /check in station/i }));
    expect(onCheckin).toHaveBeenCalledWith({
      callsign: 'WRAZ999',
      name: 'Sam',
      location: 'Elm St',
      saveContact: true,
    });
    expect(screen.getByLabelText(/callsign/i)).toHaveValue('');
    expect(screen.getByLabelText(/^name/i)).toHaveValue('');
    expect(screen.getByRole('button', { name: /check in station/i })).toBeDisabled();
  });
});
