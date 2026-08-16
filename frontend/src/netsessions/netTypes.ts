/** Display names for a session's `net_type`. Shared by the Past Nets table
 *  and the ICS-214 export so both name a net the same way. */
export const NET_TYPE_LABELS: Record<string, string> = {
  ncs: 'Net Control',
  neighborhood: 'Neighborhood',
};

/** The label for `netType`, or the raw value when it has no label yet. */
export function netTypeLabel(netType: string): string {
  return NET_TYPE_LABELS[netType] ?? netType;
}
