// AAC (Augmentative and Alternative Communication) grid types.
// The grid is stored whole in server-side per-user prefs (UserPrefs.aac_grid)
// and replaced atomically on every edit — never patched.

export interface AACButton {
  id: string;
  emoji: string;
  label: string;
  /** Text appended to the sentence strip; may contain {Name} / {callsign} tokens. */
  text: string;
}

export interface AACCategory {
  id: string;
  name: string;
  emoji: string;
  buttons: AACButton[];
}

export interface AACGrid {
  version: 1;
  categories: AACCategory[];
}

export const AAC_MAX_CATEGORIES = 20;
export const AAC_MAX_BUTTONS_PER_CATEGORY = 40;
