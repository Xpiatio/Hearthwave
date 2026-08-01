export type SortDirection = 'asc' | 'desc';

/** Rows whose string fields contain `query` (case-insensitive). Blank query passes everything. */
export function filterRoster<T extends object>(rows: T[], query: string): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((row) =>
    Object.values(row).some(
      (value) => typeof value === 'string' && value.toLowerCase().includes(needle)
    )
  );
}

/** A copy of `rows` sorted by `column`. A null column preserves the original order. */
export function sortRoster<T extends object>(
  rows: T[],
  column: keyof T | null,
  direction: SortDirection
): T[] {
  if (!column) return rows;
  const factor = direction === 'desc' ? -1 : 1;
  return [...rows].sort((a, b) => {
    const left = String(a[column] ?? '');
    const right = String(b[column] ?? '');
    return left.localeCompare(right) * factor;
  });
}
