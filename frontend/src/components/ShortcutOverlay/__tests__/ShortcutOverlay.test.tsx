import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { axe } from 'jest-axe';
import { ShortcutOverlay } from '../ShortcutOverlay';

describe('ShortcutOverlay', () => {
  it('lists the global shortcuts', () => {
    render(<ShortcutOverlay open onClose={vi.fn()} />);
    expect(screen.getByRole('dialog', { name: /keyboard shortcuts/i })).toBeInTheDocument();
    expect(screen.getByText('Esc')).toBeInTheDocument();
    expect(screen.getByText(/back to home/i)).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { baseElement } = render(<ShortcutOverlay open onClose={vi.fn()} />);
    expect(await axe(baseElement)).toHaveNoViolations();
  });
});
