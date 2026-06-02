import type { PluginDefinition, PluginProps } from '../../plugins';

interface Props extends PluginProps {
  plugin: PluginDefinition;
}

/**
 * Renders a plugin's React component with the standardized PluginProps.
 * Mount one PluginSlot per enabled plugin inside the draggable panel area.
 */
export function PluginSlot({ plugin, ...props }: Props) {
  const Component = plugin.component;
  return <Component {...props} />;
}
