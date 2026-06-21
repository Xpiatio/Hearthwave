import type React from 'react';
import type { WsMessage, Contact, UserProfile } from '../types/ws';
import type { ServerConfig } from '../components/ServerConfigPanel/ServerConfigPanel';

// Props every plugin component receives from the app shell.
export interface PluginProps {
  send: (msg: unknown) => void;
  lastMessage: WsMessage | null;
  contacts: Contact[];
  channelClear: boolean;
  transmitting: boolean;
}

// A plugin registration entry: id, display label, and the React component to mount.
export interface PluginDefinition {
  id: string;
  label: string;
  component: React.ComponentType<PluginProps>;
}

// Runtime registry — plugins add themselves here at module init time.
export const registeredPlugins: Record<string, PluginDefinition> = {};

export function registerPlugin(def: PluginDefinition): void {
  registeredPlugins[def.id] = def;
}

// ---------------------------------------------------------------------------
// TX-composition endpoint
//
// A plugin can constrain how the core message input composes an outgoing TX —
// e.g. a mesh bridge that caps message length so the packet fits one frame —
// without the input component knowing about any specific plugin. Plugins
// register a contributor; the input asks resolveTxComposition() for the active
// (most restrictive) constraint and honors it.
// ---------------------------------------------------------------------------

export interface TxComposition {
  /** Hard cap on the number of characters the user may type. */
  maxLength: number;
  /** Short label shown beside the counter (e.g. "MeshCore"). */
  hint?: string;
}

export interface TxCompositionContext {
  profile: UserProfile | null;
  serverConfig: ServerConfig;
}

export type TxCompositionContributor = (ctx: TxCompositionContext) => TxComposition | null;

const txCompositionContributors: TxCompositionContributor[] = [];

export function registerTxComposition(fn: TxCompositionContributor): void {
  txCompositionContributors.push(fn);
}

/** Drop all registered contributors. For test isolation and hot-reload. */
export function resetTxComposition(): void {
  txCompositionContributors.length = 0;
}

/** Fold candidate constraints to the most restrictive (smallest maxLength). */
export function foldCompositions(comps: (TxComposition | null)[]): TxComposition | null {
  let winner: TxComposition | null = null;
  for (const c of comps) {
    if (!c) continue;
    if (winner === null || c.maxLength < winner.maxLength) winner = c;
  }
  return winner;
}

/** Resolve the active TX constraint from all registered contributors. */
export function resolveTxComposition(ctx: TxCompositionContext): TxComposition | null {
  return foldCompositions(txCompositionContributors.map((fn) => fn(ctx)));
}
