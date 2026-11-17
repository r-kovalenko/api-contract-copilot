import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const advisory = 'https://github.com/advisories/GHSA-fc5q-39xc-vjpf';
const expires = '2026-12-01';

export function assess(report, status, production = false, today = new Date().toISOString().slice(0, 10)) {
  if (![0, 1].includes(status) || report?.error || report?.auditReportVersion !== 2 ||
      !report.vulnerabilities || !report.metadata?.dependencies?.total ||
      !report.metadata?.vulnerabilities) throw new Error('Incomplete npm audit report');
  const findings = report.vulnerabilities;
  const allowed = (name, seen = new Set()) => {
    const item = findings[name];
    if (!item || seen.has(name) || !Array.isArray(item.via) || !item.via.length) return false;
    const next = new Set([...seen, name]);
    return item.via.every(cause => typeof cause === 'string'
      ? allowed(cause, next)
      : cause.name === 'picomatch' && cause.dependency === 'picomatch' && cause.url === advisory);
  };
  const blocked = Object.entries(findings).filter(([, item]) => {
    if (!['info', 'low', 'moderate', 'high', 'critical'].includes(item.severity)) throw new Error('Unknown severity');
    return ['high', 'critical'].includes(item.severity);
  }).filter(([name]) => production || today >= expires || !allowed(name));
  if (status === 1 && Object.keys(findings).length === 0) throw new Error('Audit failed without findings');
  return blocked.map(([name]) => name);
}

function main() {
  mkdirSync('security-reports', { recursive: true });
  let failed = false;
  for (const production of [true, false]) {
    const label = production ? 'production' : 'all';
    const run = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm',
      ['audit', '--json', '--audit-level=high', ...(production ? ['--omit=dev'] : [])],
      { cwd: 'frontend', encoding: 'utf8', timeout: 180000, maxBuffer: 8 * 1024 * 1024 });
    writeFileSync(`security-reports/npm-${label}.json`, run.stdout || '');
    try {
      if (run.error || run.signal) throw new Error('npm audit execution failed');
      const blocked = assess(JSON.parse(run.stdout), run.status, production);
      if (blocked.length) throw new Error(`Blocking ${label} findings: ${blocked.join(', ')}`);
      console.log(`${label} audit passed policy. Development-only exception: ${advisory}; expires ${expires}.`);
    } catch (error) {
      console.error(error.message);
      failed = true;
    }
  }
  process.exitCode = failed ? 1 : 0;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) main();
