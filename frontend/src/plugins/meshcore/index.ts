// MeshCore plugin registration (frontend side).
//
// Importing this module once at app bootstrap registers MeshCore's TX-composition
// contributor, which caps the message input at the MeshCore packet length minus
// the sender-name prefix while the plugin is enabled.
import { registerTxComposition } from '../index';
import { meshTxContributor } from '../mesh';

registerTxComposition(
  meshTxContributor({
    enabled: (c) => c.meshcoreEnabled,
    maxLen: (c) => c.meshcoreMaxPacketLength,
    separator: (c) => c.meshcorePrefixSeparator,
    hint: 'MeshCore',
  }),
);
