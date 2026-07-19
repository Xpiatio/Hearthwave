import { render, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useRef } from 'react';
import { useSwitchScan } from '../useSwitchScan';

function Harness({ enabled, interval = 1000 }: { enabled: boolean; interval?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useSwitchScan(enabled, interval, ref);
  return (
    <div ref={ref}>
      <button data-scan="true">one</button>
      <button data-scan="true" disabled>skipped</button>
      <button data-scan="true">two</button>
      <button>not scanned</button>
    </div>
  );
}

describe('useSwitchScan', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('moves focus through enabled [data-scan] elements in order, wrapping', () => {
    const { getAllByRole } = render(<Harness enabled />);
    const [one, , two] = getAllByRole('button');
    act(() => { vi.advanceTimersByTime(1000); });
    expect(one).toHaveFocus();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(two).toHaveFocus();
    act(() => { vi.advanceTimersByTime(1000); });
    expect(one).toHaveFocus(); // wrapped, disabled button skipped
  });

  it('does nothing when disabled', () => {
    const { getAllByRole } = render(<Harness enabled={false} />);
    act(() => { vi.advanceTimersByTime(3000); });
    expect(getAllByRole('button')[0]).not.toHaveFocus();
  });

  it('stops scanning when enabled flips off', () => {
    const { rerender, getAllByRole } = render(<Harness enabled />);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(getAllByRole('button')[0]).toHaveFocus();
    rerender(<Harness enabled={false} />);
    act(() => { vi.advanceTimersByTime(5000); });
    expect(getAllByRole('button')[1]).not.toHaveFocus();
  });
});
