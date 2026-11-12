import assert from 'node:assert/strict';
import { mkdtemp, copyFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// This dependency-free starter verifies the actual compiled file in isolation.
// Add a real package-consumer smoke test if this becomes a distributed library.
const work = await mkdtemp(path.join(tmpdir(), 'artifact-smoke-'));
try {
  const target = path.join(work, 'index.mjs');
  await copyFile(new URL('../dist/index.js', import.meta.url), target);
  const { normalizeLabel } = await import(pathToFileURL(target).href);
  assert.equal(normalizeLabel(' hello  world '), 'hello world');
} finally {
  await rm(work, { recursive: true, force: true });
}
