import { useEffect } from 'react';

/**
 * Elements where Escape has its own meaning (clear/blur the field) that
 * should take priority over navigating home — most importantly, bailing a
 * user out of a mid-draft message composer would otherwise destroy the
 * draft with no way back.
 */
function isTextEntryElement(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  // target.isContentEditable isn't implemented in jsdom (used by our tests),
  // so fall back to an attribute check that works in both environments.
  if (target.isContentEditable) return true;
  const editableAncestor = target.closest('[contenteditable]');
  if (editableAncestor && editableAncestor.getAttribute('contenteditable') !== 'false') return true;
  if (target instanceof HTMLTextAreaElement) return true;
  if (target instanceof HTMLInputElement) {
    const textLikeTypes = new Set([
      'text', 'search', 'email', 'url', 'tel', 'password', 'number',
    ]);
    return textLikeTypes.has(target.type);
  }
  return false;
}

/**
 * Listens for Escape at the document level and calls onGoHome — used to let
 * an operator bail out of the desktop shell back to the HomeScreen.
 *
 * Skipped in two cases:
 *  - event.defaultPrevented: some other Escape handler (e.g. a MUI Dialog
 *    closing itself) already acted on this keypress, so we don't also
 *    navigate home on top of it.
 *  - the event target is a text-entry element (input/textarea/
 *    contenteditable): Escape there should blur/clear the field per that
 *    component's own behavior, not blow away an in-progress draft by
 *    jumping back to the HomeScreen.
 * No-ops when onGoHome is undefined (e.g. the mobile/AAC shells, which don't
 * have a home button).
 */
export function useEscapeToHome(onGoHome?: () => void): void {
  useEffect(() => {
    if (!onGoHome) return;
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Escape' || e.defaultPrevented) return;
      if (isTextEntryElement(e.target)) return;
      onGoHome!();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onGoHome]);
}
