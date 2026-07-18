import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { ConfirmDialog } from '../ConfirmDialog';

describe('ConfirmDialog', () => {
  it('fires onConfirm then closes; cancel only closes', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete it?"
        confirmLabel="Yes, delete"
        destructive
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /yes, delete/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: /no, go back/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1); // still once
    expect(onClose).toHaveBeenCalledTimes(2); // now twice
  });

  it('renders title and body', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Really?"
        body="This is important."
        confirmLabel="Yes"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    expect(screen.getByText('Really?')).toBeInTheDocument();
    expect(screen.getByText('This is important.')).toBeInTheDocument();
  });

  it('defaults cancelLabel to "No, go back"', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Exit?"
        confirmLabel="Yes, exit"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    expect(screen.getByRole('button', { name: /no, go back/i })).toBeInTheDocument();
  });

  it('uses custom cancelLabel when provided', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete?"
        confirmLabel="Yes, delete"
        cancelLabel="Keep it"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    expect(screen.getByRole('button', { name: /keep it/i })).toBeInTheDocument();
  });

  it('renders confirm button with error color when destructive=true', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete?"
        confirmLabel="Yes, delete"
        destructive
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    const confirmButton = screen.getByRole('button', { name: /yes, delete/i });
    expect(confirmButton).toHaveClass('MuiButton-colorError');
  });

  it('renders confirm button with primary color when destructive=false', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Submit?"
        confirmLabel="Yes, submit"
        destructive={false}
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    const confirmButton = screen.getByRole('button', { name: /yes, submit/i });
    expect(confirmButton).toHaveClass('MuiButton-colorPrimary');
  });

  it('is hidden when open=false', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open={false}
        title="Delete?"
        confirmLabel="Yes, delete"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    expect(screen.queryByText('Delete?')).not.toBeInTheDocument();
  });

  it('switch scanning cycles the two buttons while open', () => {
    vi.useFakeTimers();
    render(<ConfirmDialog open title="Sure?" confirmLabel="Yes, do it"
      switchScan switchScanIntervalS={1} onConfirm={vi.fn()} onClose={vi.fn()} />);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: /yes, do it/i })).toHaveFocus();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByRole('button', { name: /no, go back/i })).toHaveFocus();
    vi.useRealTimers();
  });

  it('passes a11y checks', async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    const { container } = render(
      <ConfirmDialog
        open
        title="Delete it?"
        body="This cannot be undone."
        confirmLabel="Yes, delete"
        cancelLabel="No, keep it"
        destructive
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
