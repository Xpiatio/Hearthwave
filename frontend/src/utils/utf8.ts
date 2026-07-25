// UTF-8 byte helpers — the browser-side mirror of the backend's mesh clamp
// (MeshForwarderPlugin._clamp_utf8_bytes). Mesh radios measure their packet limit
// in bytes on the wire, not characters, so a cap counted in characters lets the
// operator type text the backend then silently truncates.

const encoder = new TextEncoder();

/** Length of `s` in UTF-8 bytes. */
export function utf8Len(s: string): number {
  return encoder.encode(s).length;
}

/** Truncate `s` to at most `maxBytes` UTF-8 bytes, never splitting a code point. */
export function clampUtf8Bytes(s: string, maxBytes: number): string {
  if (maxBytes <= 0) return '';
  if (utf8Len(s) <= maxBytes) return s;
  // Walk by code point (the string iterator yields whole surrogate pairs) and stop
  // before the one that would cross the cap, so the result is always valid UTF-8.
  let out = '';
  let used = 0;
  for (const ch of s) {
    const size = utf8Len(ch);
    if (used + size > maxBytes) break;
    out += ch;
    used += size;
  }
  return out;
}
