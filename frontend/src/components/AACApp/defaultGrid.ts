import type { AACButton, AACCategory, AACGrid } from '../../types/aac';
import { AAC_MAX_BUTTONS_PER_CATEGORY, AAC_MAX_CATEGORIES } from '../../types/aac';

let counter = 0;
export function newId(prefix: string): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  counter += 1;
  return `${prefix}-${Date.now()}-${counter}`;
}

function btn(emoji: string, label: string, text?: string): AACButton {
  return { id: newId('b'), emoji, label, text: text ?? label };
}

export function makeDefaultGrid(): AACGrid {
  return {
    version: 1,
    categories: [
      {
        id: newId('c'),
        name: 'Core',
        emoji: '⭐',
        buttons: [
          btn('👍', 'Yes'),
          btn('👎', 'No'),
          btn('🆘', 'Help', 'I need help'),
          btn('🙏', 'Please'),
          btn('😊', 'Thank you'),
          btn('✋', 'Wait', 'Please wait'),
          btn('➕', 'More'),
          btn('✅', 'Done', 'I am done'),
        ],
      },
      {
        id: newId('c'),
        name: 'Radio',
        emoji: '📻',
        buttons: [
          btn('📻', 'Check in', 'This is {callsign} checking in'),
          btn('👌', 'QSL', 'QSL'),
          btn('🔁', 'Say again', 'Please repeat your last transmission'),
          btn('🕐', 'Standing by', 'Standing by'),
          btn('👋', '73', '73'),
          btn('📋', 'Copy that', 'Copy that'),
          btn('❌', 'Negative copy', 'Negative copy, please repeat'),
          btn('🏁', 'Clear', '{callsign} clear'),
        ],
      },
      {
        id: newId('c'),
        name: 'Status',
        emoji: '💬',
        buttons: [
          btn('🙂', 'I am okay', 'I am okay'),
          btn('🚨', 'Need assistance', 'I need assistance'),
          btn('📶', 'Good signal', 'Your signal is good'),
          btn('📉', 'Weak signal', 'Your signal is weak'),
        ],
      },
      {
        id: newId('c'),
        name: 'About me',
        emoji: '🙋',
        buttons: [
          btn('🙋', 'My name', 'My name is {Name}'),
          btn('🎙️', 'My callsign', 'My callsign is {callsign}'),
        ],
      },
    ],
  };
}

function sanitizeButton(raw: unknown): AACButton | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const r = raw as Record<string, unknown>;
  const label = typeof r.label === 'string' ? r.label.trim() : '';
  const text = typeof r.text === 'string' ? r.text.trim() : '';
  if (!label && !text) return null;
  return {
    id: typeof r.id === 'string' && r.id ? r.id : newId('b'),
    emoji: typeof r.emoji === 'string' ? r.emoji : '💬',
    label: label || text,
    text: text || label,
  };
}

function sanitizeCategory(raw: unknown): AACCategory | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.name !== 'string' || !r.name.trim()) return null;
  const buttons = Array.isArray(r.buttons)
    ? r.buttons
        .map(sanitizeButton)
        .filter((b): b is AACButton => b !== null)
        .slice(0, AAC_MAX_BUTTONS_PER_CATEGORY)
    : [];
  return {
    id: typeof r.id === 'string' && r.id ? r.id : newId('c'),
    name: r.name.trim(),
    emoji: typeof r.emoji === 'string' ? r.emoji : '📁',
    buttons,
  };
}

/**
 * Defensive load of a grid coming from server prefs. Falls back to the
 * default grid on null/garbage/unknown version, so a corrupt pref can
 * never brick the AAC screen.
 */
export function sanitizeAacGrid(raw: unknown): AACGrid {
  if (typeof raw !== 'object' || raw === null) return makeDefaultGrid();
  const r = raw as Record<string, unknown>;
  if (r.version !== 1 || !Array.isArray(r.categories)) return makeDefaultGrid();
  const categories = r.categories
    .map(sanitizeCategory)
    .filter((c): c is AACCategory => c !== null)
    .slice(0, AAC_MAX_CATEGORIES);
  if (categories.length === 0) return makeDefaultGrid();
  return { version: 1, categories };
}

/**
 * Resolve {Name} / {callsign} tokens (case-insensitive) and strip any other
 * {...} tokens so the server's TokenPromptDialog flow — a typing dialog —
 * never fires for an AAC user.
 */
export function resolveTokens(text: string, operatorName: string, callsign: string): string {
  return text
    .replace(/{Name}/gi, operatorName || 'Operator')
    .replace(/{callsign}/gi, callsign || 'my callsign')
    .replace(/{[^}]*}/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}
