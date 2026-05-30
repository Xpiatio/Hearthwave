import { useState, useCallback } from 'react';

export interface Operator {
  operatorName: string;
  callsign: string;
  location: string;
}

const STORAGE_KEY = 'radio_tty_operator';

function loadFromStorage(): Operator | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Operator;
  } catch {
    return null;
  }
}

export function useOperator() {
  const [operator, setOperatorState] = useState<Operator | null>(loadFromStorage);

  const setOperator = useCallback((op: Operator) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(op));
    setOperatorState(op);
  }, []);

  const clearOperator = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setOperatorState(null);
  }, []);

  return { operator, setOperator, clearOperator };
}
