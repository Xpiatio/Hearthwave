import { render as rtlRender, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { IncidentDialog, INCIDENT_CATEGORIES } from '../IncidentDialog';
import type { IncidentReportPayload } from '../IncidentDialog';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

function makeProps(overrides: Partial<{
  open: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (p: IncidentReportPayload) => void;
}> = {}) {
  return {
    open: true,
    error: null,
    onClose: vi.fn(),
    onSubmit: vi.fn(),
    ...overrides,
  };
}

describe('IncidentDialog', () => {
  it('exposes exactly the five plain-language categories', () => {
    expect(INCIDENT_CATEGORIES.map((c) => c.label)).toEqual([
      'Suspicious activity', 'Hazard', 'Medical', 'Lost pet or person', 'Utility outage',
    ]);
  });

  it('renders nothing when closed', () => {
    render(<IncidentDialog {...makeProps({ open: false })} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('disables submit until description and location are both filled', async () => {
    const user = userEvent.setup();
    render(<IncidentDialog {...makeProps()} />);
    const submit = screen.getByRole('button', { name: 'Send report' });
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText(/what happened/i), 'Downed power line');
    expect(submit).toBeDisabled();

    await user.type(screen.getByLabelText(/location/i), 'Corner of 5th and Main');
    expect(submit).not.toBeDisabled();
  });

  it('submits the default category when the user never changes the Select', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<IncidentDialog {...props} />);

    await user.type(screen.getByLabelText(/what happened/i), 'Suspicious van parked for hours');
    await user.type(screen.getByLabelText(/location/i), 'Elm St');
    await user.click(screen.getByRole('button', { name: 'Send report' }));

    expect(props.onSubmit).toHaveBeenCalledWith({
      category: 'suspicious',
      description: 'Suspicious van parked for hours',
      location: 'Elm St',
    });
  });

  it('trims description and location before submitting', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<IncidentDialog {...props} />);

    await user.type(screen.getByLabelText(/what happened/i), '  Tree down  ');
    await user.type(screen.getByLabelText(/location/i), '  Oak St  ');
    await user.click(screen.getByRole('button', { name: 'Send report' }));

    expect(props.onSubmit).toHaveBeenCalledWith({
      category: 'suspicious',
      description: 'Tree down',
      location: 'Oak St',
    });
  });

  it('cancel button calls onClose', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<IncidentDialog {...props} />);
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(props.onClose).toHaveBeenCalledOnce();
  });

  it('displays a server-side error', () => {
    render(<IncidentDialog {...makeProps({ error: 'Location must be 200 characters or fewer.' })} />);
    expect(screen.getByText('Location must be 200 characters or fewer.')).toBeInTheDocument();
  });

  it('has no axe violations while open', async () => {
    const { container } = render(<IncidentDialog {...makeProps()} />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no axe violations while open with an error shown', async () => {
    const { container } = render(<IncidentDialog {...makeProps({ error: 'Description is required.' })} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
