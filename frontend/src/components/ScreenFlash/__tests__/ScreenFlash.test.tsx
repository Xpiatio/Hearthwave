import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { axe } from 'jest-axe';
import { ScreenFlash } from '../ScreenFlash';

describe('ScreenFlash', () => {
  it('renders nothing when no flash', () => {
    const { container } = render(<ScreenFlash flash={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders an aria-hidden non-interactive overlay keyed by seq', () => {
    const { container, rerender } = render(<ScreenFlash flash={{ kind: 'street', seq: 1 }} />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.getAttribute('aria-hidden')).toBe('true');
    expect(el.style.pointerEvents).toBe('none');
    rerender(<ScreenFlash flash={{ kind: 'street', seq: 2 }} />);
    expect(container.firstElementChild).not.toBe(el); // key change restarts the animation
  });

  it('has no axe violations', async () => {
    const { container } = render(<ScreenFlash flash={{ kind: 'rx', seq: 1 }} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
