/** Fixed dusk rule: dark 19:00-06:59 local. A wall display has no user
 *  pref surface, so a predictable rule beats a configurable one (YAGNI —
 *  revisit if households ask for sunset-accurate switching). */
export function isDuskDark(now: Date): boolean {
  const h = now.getHours();
  return h >= 19 || h < 7;
}
