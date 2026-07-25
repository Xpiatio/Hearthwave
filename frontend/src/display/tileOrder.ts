import type { FamilyPresenceEntry } from '../types/ws';

/** Apply a display's hand-sorted tile order to the live presence list.
 *
 *  The stored order is advisory, never authoritative: the server's presence
 *  list decides who exists. Ids that are in the order but no longer present
 *  are dropped, and anyone the order has never seen — a family member added
 *  after the last drag — is appended in server order rather than vanishing.
 */
export function applyTileOrder(
  presence: FamilyPresenceEntry[],
  order: string[],
): FamilyPresenceEntry[] {
  if (!order.length) return presence;

  const byId = new Map(presence.map((e) => [e.user_id, e]));
  const ordered: FamilyPresenceEntry[] = [];
  const placed = new Set<string>();

  for (const id of order) {
    const entry = byId.get(id);
    if (entry && !placed.has(id)) {
      ordered.push(entry);
      placed.add(id);
    }
  }

  for (const entry of presence) {
    if (!placed.has(entry.user_id)) ordered.push(entry);
  }

  return ordered;
}

/** Move `activeId` to `overId`'s slot, returning the new id list.
 *
 *  Split out from the drag handler so the reordering itself is testable —
 *  jsdom has no layout, so dnd-kit's own drag cannot be exercised there.
 *  Returns the original list unchanged if either id is missing.
 */
export function reorderIds(ids: string[], activeId: string, overId: string): string[] {
  const from = ids.indexOf(activeId);
  const to = ids.indexOf(overId);
  if (from < 0 || to < 0 || from === to) return ids;
  const next = ids.slice();
  next.splice(to, 0, next.splice(from, 1)[0]);
  return next;
}
