import { render as rtlRender, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { PresetComposer } from '../PresetComposer';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

describe('PresetComposer', () => {
  it('renders one button per preset', () => {
    render(<PresetComposer quickMessages={['Standing by', 'QSL']} onSend={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Standing by' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'QSL' })).toBeInTheDocument();
  });

  it('sends the exact preset text with no trimming or decoration', () => {
    const onSend = vi.fn();
    render(<PresetComposer quickMessages={['Heading home now']} onSend={onSend} />);
    fireEvent.click(screen.getByRole('button', { name: 'Heading home now' }));
    expect(onSend).toHaveBeenCalledWith('Heading home now', '', '');
  });

  it('has no axe violations', async () => {
    const { container } = render(
      <PresetComposer quickMessages={['Standing by', 'QSL']} onSend={vi.fn()} />
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it('renders an empty-state message instead of a dead zero-button row when there are no presets', () => {
    render(<PresetComposer quickMessages={[]} onSend={vi.fn()} />);
    expect(screen.getByText('Ask an adult to set up your messages.')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('empty state has no axe violations', async () => {
    const { container } = render(<PresetComposer quickMessages={[]} onSend={vi.fn()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
