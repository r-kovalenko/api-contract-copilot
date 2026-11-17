import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assess } from './audit_frontend.mjs';
const cause = { name: 'picomatch', dependency: 'picomatch', url: 'https://github.com/advisories/GHSA-fc5q-39xc-vjpf' };
function report() {
  return { auditReportVersion: 2, metadata: { dependencies: { total: 10 }, vulnerabilities: { high: 2 } },
    vulnerabilities: { picomatch: { severity: 'high', via: [cause] }, vite: { severity: 'high', via: ['picomatch'] } } };
}
test('temporary exception follows only the named advisory through dependency chains', () => {
  assert.deepEqual(assess(report(), 1, false, '2026-11-17'), []);
  assert.equal(assess(report(), 1, true, '2026-11-17').length, 2);
  assert.equal(assess(report(), 1, false, '2026-12-01').length, 2);
});
test('additional advisory, missing dependency and cycles fail closed', () => {
  for (const extra of [{ ...cause, url: 'https://example.com/other' }, 'missing', 'vite']) {
    const value = report(); value.vulnerabilities.picomatch.via.push(extra);
    assert.equal(assess(value, 1, false, '2026-11-17').length, 2);
  }
});
test('operational errors and incomplete reports fail closed', () => {
  for (const value of [{}, { ...report(), error: {} }, { ...report(), auditReportVersion: 3 }]) {
    assert.throws(() => assess(value, 1));
  }
  assert.throws(() => assess(report(), 2));
  const value = report(); value.vulnerabilities = {};
  assert.throws(() => assess(value, 1));
  assert.deepEqual(assess(value, 0), []);
});
