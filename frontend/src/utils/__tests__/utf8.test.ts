import { describe, it, expect } from 'vitest';
import { utf8Len, clampUtf8Bytes } from '../utf8';

describe('utf8Len', () => {
  it('counts ASCII as one byte each', () => {
    expect(utf8Len('hello')).toBe(5);
  });

  it('counts multibyte characters by their encoded size', () => {
    expect(utf8Len('é')).toBe(2);
    expect(utf8Len('→')).toBe(3);
    expect(utf8Len('🛰')).toBe(4);
  });

  it('is zero for the empty string', () => {
    expect(utf8Len('')).toBe(0);
  });
});

describe('clampUtf8Bytes', () => {
  it('returns the input untouched when it already fits', () => {
    expect(clampUtf8Bytes('hello', 10)).toBe('hello');
    expect(clampUtf8Bytes('hello', 5)).toBe('hello');
  });

  it('truncates ASCII at the byte cap', () => {
    expect(clampUtf8Bytes('0123456789', 4)).toBe('0123');
  });

  it('never splits a multibyte character', () => {
    // Each "é" is 2 bytes: a 3-byte cap fits one, not one-and-a-half.
    expect(clampUtf8Bytes('ééé', 3)).toBe('é');
    expect(utf8Len(clampUtf8Bytes('ééé', 3))).toBeLessThanOrEqual(3);
  });

  it('keeps surrogate pairs whole', () => {
    // A 4-byte emoji does not fit in 3 bytes, and half a pair is never emitted.
    expect(clampUtf8Bytes('🛰', 3)).toBe('');
    expect(clampUtf8Bytes('a🛰', 5)).toBe('a🛰');
  });

  it('returns empty for a non-positive cap', () => {
    expect(clampUtf8Bytes('hello', 0)).toBe('');
    expect(clampUtf8Bytes('hello', -1)).toBe('');
  });
});
