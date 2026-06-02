import type React from 'react';
import type { WsMessage, Contact } from '../types/ws';

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
