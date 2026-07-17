import { render as rtlRender, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { ConfigPanel } from '../ConfigPanel';
import type { InputDeviceOption, MonitorSinkOption, OutputDeviceOption } from '../../../types/ws';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

const DEVICE_OPTIONS: InputDeviceOption[] = [
  { label: 'Built-in Microphone', id: 0 },
];
const SINK_OPTIONS: MonitorSinkOption[] = [];
const OUTPUT_DEVICE_OPTIONS: OutputDeviceOption[] = [
  { label: 'System Default (speaker)', id: -1 },
];

function makeBaseProps() {
  return {
    filterProfanity: false,
    aacMode: false,
    fuzzyCallsign: false,
    fuzzyCallsignRewrite: false,
    inputDevice: 0 as string | number,
    systemMonitorSink: '',
    inputDevices: DEVICE_OPTIONS,
    monitorSinks: SINK_OPTIONS,
    outputDevice: -1,
    outputDevices: OUTPUT_DEVICE_OPTIONS,
    spectroColormap: 'viridis' as const,
    spectroFreqRange: 'voice' as const,
    spectroTimeWindowS: 30,
    uiLevel: 'operator' as const,
    fontScale: 1,
    highContrast: false,
    onToggleProfanity: vi.fn(),
    onToggleAacMode: vi.fn(),
    onToggleFuzzy: vi.fn(),
    onToggleFuzzyRewrite: vi.fn(),
    onInputDeviceChange: vi.fn(),
    onOutputDeviceChange: vi.fn(),
    onSpectroColormapChange: vi.fn(),
    onSpectroFreqRangeChange: vi.fn(),
    onSpectroTimeWindowChange: vi.fn(),
    onUiLevelChange: vi.fn(),
    onFontScaleChange: vi.fn(),
    onToggleHighContrast: vi.fn(),
  };
}

const baseProps = makeBaseProps();

describe('ConfigPanel — interface tier + accessibility controls', () => {
  it('renders the Interface toggle group reflecting uiLevel', () => {
    render(<ConfigPanel {...baseProps} uiLevel="simple" />);
    expect(screen.getByRole('button', { name: /simple interface/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: /operator interface/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('fires onUiLevelChange when the Operator button is clicked', () => {
    const onUiLevelChange = vi.fn();
    render(<ConfigPanel {...baseProps} uiLevel="simple" onUiLevelChange={onUiLevelChange} />);
    fireEvent.click(screen.getByRole('button', { name: /operator interface/i }));
    expect(onUiLevelChange).toHaveBeenCalledWith('operator');
  });

  it('fires onFontScaleChange when a text size button is clicked', () => {
    const onFontScaleChange = vi.fn();
    render(<ConfigPanel {...baseProps} fontScale={1} onFontScaleChange={onFontScaleChange} />);
    fireEvent.click(screen.getByRole('button', { name: /150% text size/i }));
    expect(onFontScaleChange).toHaveBeenCalledWith(1.5);
  });

  it('fires onToggleHighContrast', () => {
    const onToggleHighContrast = vi.fn();
    render(<ConfigPanel {...baseProps} onToggleHighContrast={onToggleHighContrast} />);
    fireEvent.click(screen.getByLabelText(/high contrast/i));
    expect(onToggleHighContrast).toHaveBeenCalled();
  });

  it('has no axe violations', async () => {
    const { container } = render(<ConfigPanel {...baseProps} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
