import { useEffect, useMemo, useState } from 'react';

export type SortDirection = 'asc' | 'desc';

/** Minimum row count at which the filter box appears on its own; below that
 *  it only shows once a query has actually been typed (see `useRosterSort`). */
const ROW_COUNT_FILTER_THRESHOLD = 2;

/** Rows where at least one of `keys` contains `query` (case-insensitive).
 *  Blank query passes everything. `keys` is explicit — pass only the fields
 *  the table actually renders, so a query never matches a hidden field like
 *  an internal id or a raw timestamp the user can't see.
 *
 *  Non-string fields are matched against their rendered text, not their raw
 *  value: a boolean flag (e.g. `no_answer`) renders as "yes" when true and ""
 *  when false (see PastNetsTab / csv.ts), so `true` matches "yes" and `false`
 *  never matches anything — the same rule that keeps a hidden field from
 *  matching applies to a value whose on-screen text differs from its type. */
export function filterRoster<T extends object>(
  rows: T[],
  query: string,
  keys: (keyof T)[],
): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((row) =>
    keys.some((key) => {
      const value = row[key];
      if (typeof value === 'string') return value.toLowerCase().includes(needle);
      if (typeof value === 'boolean') return value && 'yes'.includes(needle);
      return false;
    }),
  );
}

/** A copy of `rows` sorted by `column`. A null column preserves the original order. */
export function sortRoster<T extends object>(
  rows: T[],
  column: keyof T | null,
  direction: SortDirection,
): T[] {
  if (!column) return rows;
  const factor = direction === 'desc' ? -1 : 1;
  return [...rows].sort((a, b) => {
    const left = String(a[column] ?? '');
    const right = String(b[column] ?? '');
    return left.localeCompare(right) * factor;
  });
}

export interface RosterSort<T, C extends keyof T & string> {
  rosterQuery: string;
  setRosterQuery: (value: string) => void;
  sortColumn: C | null;
  setSortColumn: (value: C | null) => void;
  sortDirection: SortDirection;
  setSortDirection: (value: SortDirection | ((d: SortDirection) => SortDirection)) => void;
  /** Toggle-on-repeat-click sort handler for a clickable column header. */
  handleSort: (column: C) => void;
  /** `rows` filtered by `rosterQuery` (over `searchKeys`) and sorted by `sortColumn`/`sortDirection`. */
  visibleRoster: T[];
  /** Whether the filter input should be shown. True once there are enough
   *  rows to be worth filtering, OR a query is already typed — so a filter
   *  that has thinned the roster below the row-count threshold can never
   *  make its own clear-the-filter control disappear. */
  showFilterInput: boolean;
}

/**
 * Shared filter/sort state for a roster table (used by PastNetsTab, NCSPanel,
 * and NeighborhoodPanel's RosterList).
 *
 * `resetKey` — typically the id of whatever the roster belongs to (e.g. a
 * selected past session) — clears the query and sort whenever it changes, so
 * switching to a different roster never inherits a filter/sort the new
 * roster has no control left to clear. Omit it for a live roster with no
 * such "switched to a different one" moment (e.g. an in-progress net).
 */
export function useRosterSort<T extends object, C extends keyof T & string>(
  rows: T[],
  searchKeys: (keyof T)[],
  resetKey?: unknown,
): RosterSort<T, C> {
  const [rosterQuery, setRosterQuery] = useState('');
  const [sortColumn, setSortColumn] = useState<C | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  useEffect(() => {
    setRosterQuery('');
    setSortColumn(null);
    setSortDirection('asc');
  }, [resetKey]);

  function handleSort(column: C) {
    if (sortColumn === column) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  }

  const visibleRoster = useMemo(
    () => sortRoster(filterRoster(rows, rosterQuery, searchKeys), sortColumn, sortDirection),
    [rows, rosterQuery, sortColumn, sortDirection, searchKeys],
  );

  return {
    rosterQuery,
    setRosterQuery,
    sortColumn,
    setSortColumn,
    sortDirection,
    setSortDirection,
    handleSort,
    visibleRoster,
    showFilterInput: rows.length > ROW_COUNT_FILTER_THRESHOLD || rosterQuery !== '',
  };
}
