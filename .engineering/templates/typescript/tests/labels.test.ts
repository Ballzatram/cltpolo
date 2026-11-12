import { describe, expect, it } from 'vitest';
import { normalizeLabel } from '../src/index.js';

describe('normalizeLabel', () => {
  it.each([
    ['  hello   world  ', 'hello world'],
    ['hello', 'hello'],
    ['a\nb', 'a b'],
  ])('normalizes %j', (input, expected) => {
    expect(normalizeLabel(input)).toBe(expected);
  });

  it.each(['', ' ', '\t\n'])('rejects an empty label %j', (input) => {
    expect(() => normalizeLabel(input)).toThrow('must not be empty');
  });
});
