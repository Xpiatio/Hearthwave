import { useEffect } from 'react';

/**
 * Listens for Escape at the document level and calls onGoHome — used to let
 * an operator bail out of the desktop shell back to the HomeScreen.
 *
 * Guarded by event.defaultPrevented: MUI's Modal component (which backs
 * Dialog, Menu, etc.) calls stopPropagation — not preventDefault — on its own
 * Escape handling, so this listener would still fire while a dialog is open
 * on a strict reading of the DOM event. In practice the dialog's own
 * onClose/Escape handling runs first and closes it, and this is harmless
 * defense in the rare case some other listener does call preventDefault.
 * No-ops when onGoHome is undefined (e.g. the mobile/AAC shells, which don't
 * have a home button).
 */
export function useEscapeToHome(onGoHome?: () => void): void {
  useEffect(() => {
    if (!onGoHome) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !e.defaultPrevented) onGoHome!();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onGoHome]);
}
