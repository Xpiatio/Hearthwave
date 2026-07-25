// Frontend plugin support — fully declarative.
//
// Plugins ship NO browser code. The backend broadcasts each plugin's manifest
// (config schema + capabilities) in the status message; the app renders settings
// generically (see PluginConfigForm) and resolves TX-input constraints from the
// declarative `tx_composition` capability here. There is no runtime JS loading.
import type { PluginManifest, UserProfile, WsMessage, Contact } from '../types/ws';
import { utf8Len } from '../utils/utf8';

// Props the app shell passes to a built-in panel component (e.g. NCSPanel).
// Third-party plugins do NOT ship components — this is for in-tree panels only.
export interface PluginProps {
  send: (msg: unknown) => void;
  lastMessage: WsMessage | null;
  contacts: Contact[];
  channelClear: boolean;
  transmitting: boolean;
}

export interface TxComposition {
  /** Hard cap on the message size in UTF-8 bytes — the unit the mesh radios and the
   *  backend clamp both measure (see utils/utf8 and mesh_forwarder.py). */
  maxBytes: number;
  /** Short label shown beside the counter (e.g. "MeshCore"). */
  hint?: string;
}

/** Fold candidate constraints to the most restrictive (smallest maxBytes). */
export function foldCompositions(comps: (TxComposition | null)[]): TxComposition | null {
  let winner: TxComposition | null = null;
  for (const c of comps) {
    if (!c) continue;
    if (winner === null || c.maxBytes < winner.maxBytes) winner = c;
  }
  return winner;
}

function senderName(profile: UserProfile | null): string {
  return profile?.display_name || profile?.operator_name || profile?.callsign || '';
}

/** A mesh-bridge-style plugin reserves room for the "<name><sep>" prefix it adds,
 *  so the message input is capped at max_packet_length minus that prefix. Both the
 *  packet limit and the prefix are counted in UTF-8 bytes, matching the backend
 *  clamp — a multibyte name eats more of the packet than its character count. */
function compositionForPlugin(
  plugin: PluginManifest,
  profile: UserProfile | null,
): TxComposition | null {
  const tx = plugin.tx_composition;
  if (!plugin.enabled || !tx) return null;
  const maxLen = Number(plugin.config[tx.max_len_key]);
  if (!Number.isFinite(maxLen)) return null;
  const separator = String(plugin.config[tx.separator_key] ?? '');
  const name = senderName(profile);
  const prefixBytes = name ? utf8Len(name) + utf8Len(separator) : 0;
  return { maxBytes: Math.max(1, maxLen - prefixBytes), hint: tx.hint };
}

/** Resolve the active TX-input constraint from all enabled plugins' declared
 *  tx_composition capabilities (most restrictive wins). */
export function resolveTxComposition(
  plugins: PluginManifest[],
  profile: UserProfile | null,
): TxComposition | null {
  return foldCompositions(plugins.map((p) => compositionForPlugin(p, profile)));
}

/** Whether a plugin (by id) is present and enabled — gates plugin UI (e.g. NCS). */
export function isPluginEnabled(plugins: PluginManifest[], id: string): boolean {
  return plugins.some((p) => p.id === id && p.enabled);
}
