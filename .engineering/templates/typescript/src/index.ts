/** Collapse whitespace and reject a label with no visible characters. */
export function normalizeLabel(value: string): string {
  const normalized = value.trim().split(/\s+/u).join(' ');
  if (!normalized) {
    throw new Error('Label must not be empty');
  }
  return normalized;
}
