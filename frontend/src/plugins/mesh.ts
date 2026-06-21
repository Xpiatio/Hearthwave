// Shared helper for mesh-bridge plugins (MeshCore today, Meshtastic later).
//
// Every mesh bridge forwards a TX prefixed with the sender's name, so the
// message input must reserve room for that prefix. This builds the
// TxCompositionContributor that does the prefix-length math; each plugin
// supplies accessors for its own config keys plus a display hint.
import type { ServerConfig } from '../components/ServerConfigPanel/ServerConfigPanel';
import type { TxCompositionContributor } from './index';

export interface MeshTxOptions {
  enabled: (c: ServerConfig) => boolean;
  maxLen: (c: ServerConfig) => number;
  separator: (c: ServerConfig) => string;
  hint: string;
}

export function meshTxContributor(opts: MeshTxOptions): TxCompositionContributor {
  return ({ profile, serverConfig }) => {
    if (!opts.enabled(serverConfig)) return null;
    const name = profile?.display_name || profile?.operator_name || profile?.callsign || '';
    const prefixLen = name ? name.length + opts.separator(serverConfig).length : 0;
    return {
      maxLength: Math.max(1, opts.maxLen(serverConfig) - prefixLen),
      hint: opts.hint,
    };
  };
}
