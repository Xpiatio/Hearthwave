import { render as rtlRender, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { makeTheme } from '../../../theme';
import { describe, it, expect, vi } from 'vitest';
import { CalibrationDialog } from '../CalibrationDialog';
import type { WsMessage } from '../../../types/ws';

function render(ui: React.ReactElement) {
  return rtlRender(<ThemeProvider theme={makeTheme(false)}>{ui}</ThemeProvider>);
}

function makeProps(overrides: Partial<Parameters<typeof CalibrationDialog>[0]> = {}) {
  return {
    open: true,
    onClose: vi.fn(),
    send: vi.fn(),
    lastMessage: null as WsMessage | null,
    ...overrides,
  };
}

describe('CalibrationDialog', () => {
  it('requests the passage text when opened', () => {
    const send = vi.fn();
    render(<CalibrationDialog {...makeProps({ send })} />);
    expect(send).toHaveBeenCalledWith({ type: 'calibration_get_text' });
  });

  it('does not render content when closed', () => {
    render(<CalibrationDialog {...makeProps({ open: false })} />);
    expect(screen.queryByText('STT Calibration')).not.toBeInTheDocument();
  });

  it('shows the fetched passage and enables Start once loaded', () => {
    const { rerender } = render(<CalibrationDialog {...makeProps()} />);
    expect(screen.getByRole('button', { name: 'Start Recording' })).toBeDisabled();
    rerender(
      <ThemeProvider theme={makeTheme(false)}>
        <CalibrationDialog {...makeProps({ lastMessage: { type: 'calibration_text', text: 'When in the Course...' } })} />
      </ThemeProvider>
    );
    expect(screen.getByText('When in the Course...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start Recording' })).toBeEnabled();
  });

  it('sends calibration_start when Start Recording is clicked', () => {
    const send = vi.fn();
    render(
      <CalibrationDialog
        {...makeProps({ send, lastMessage: { type: 'calibration_text', text: 'passage' } })}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: 'Start Recording' }));
    expect(send).toHaveBeenCalledWith({ type: 'calibration_start' });
  });

  it('moves to the recording step on calibration_started', () => {
    render(<CalibrationDialog {...makeProps({ lastMessage: { type: 'calibration_started' } })} />);
    expect(screen.getByText(/Recording…/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Stop & Analyze' })).toBeInTheDocument();
  });

  it('sends calibration_stop when Stop & Analyze is clicked', () => {
    const send = vi.fn();
    render(<CalibrationDialog {...makeProps({ send, lastMessage: { type: 'calibration_started' } })} />);
    fireEvent.click(screen.getByRole('button', { name: 'Stop & Analyze' }));
    expect(send).toHaveBeenCalledWith({ type: 'calibration_stop' });
  });

  it('shows sweep progress on calibration_progress', () => {
    render(
      <CalibrationDialog
        {...makeProps({
          lastMessage: {
            type: 'calibration_progress', index: 2, total: 6,
            model: 'small.en', gain_mode: 'agc', noise_profile: false,
            wer: 0, hypothesis: '',
          },
        })}
      />
    );
    expect(screen.getByText(/small\.en/)).toBeInTheDocument();
    expect(screen.getByText(/\(2\/6\)/)).toBeInTheDocument();
  });

  it('shows a ranked results table on calibration_result, flagging the recommended row', () => {
    const results = [
      { model: 'small.en', gain_mode: 'agc', noise_profile: false, wer: 0.05, hypothesis: 'x' },
      { model: 'tiny.en', gain_mode: 'off', noise_profile: true, wer: 0.4, hypothesis: 'y' },
    ];
    render(
      <CalibrationDialog
        {...makeProps({
          lastMessage: { type: 'calibration_result', results, recommended: results[0] },
        })}
      />
    );
    expect(screen.getByText('5.0%')).toBeInTheDocument();
    expect(screen.getByText('40.0%')).toBeInTheDocument();
    expect(screen.getByText('Recommended')).toBeInTheDocument();
  });

  it('sends calibration_apply with the chosen combo when a row Apply is clicked', () => {
    const send = vi.fn();
    const results = [
      { model: 'small.en', gain_mode: 'agc', noise_profile: false, wer: 0.05, hypothesis: 'x' },
    ];
    render(
      <CalibrationDialog
        {...makeProps({
          send,
          lastMessage: { type: 'calibration_result', results, recommended: results[0] },
        })}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    expect(send).toHaveBeenCalledWith({
      type: 'calibration_apply', whisper_model: 'small.en', gain_mode: 'agc', noise_profile: false,
    });
  });

  it('shows an error banner on calibration_error without losing the current step', () => {
    render(
      <CalibrationDialog
        {...makeProps({ lastMessage: { type: 'calibration_error', detail: 'No audio captured.' } })}
      />
    );
    expect(screen.getByText('No audio captured.')).toBeInTheDocument();
  });
});
