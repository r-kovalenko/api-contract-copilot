// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReportDetails, ReportWorkspace } from './ReportWorkspace';
import { type AnalysisReport } from './analyses';
const project = { id: 'p1', name: 'Demo', description: null, created_at: '2026-01-01' };
const malicious = '<img src=x onerror=alert(1)>';
const saved: AnalysisReport = {
  id: 'run1', project_id: 'p1', comparison_id: 'c1', change_id: 'change1', created_at: '2026-01-01',
  request: { comparison_id: 'c1', change_id: 'change1', code_query: 'name', knowledge_query: 'name' },
  report: {
    status: 'partial', severity: 'breaking', summary: malicious, api_version: 'v2', model_status: 'offline', evidence_gaps: ['code_coverage_incomplete'],
    change: { id: 'change1', summary: 'Removed', rule_id: 'removed', severity: 'breaking', operation: 'GET', path: '/customers', section: 'response', evidence: { text: 'Contract evidence' } },
    affected_files: [{ path: 'client.py', line: 4, source_id: 'code1' }],
    recommendations: [{ text: 'Review usage', source_ids: ['code1', 'missing'] }],
    model_observations: [{ text: malicious, source_ids: ['doc1'] }],
    code: { repository: 'consumer', query: 'name', truncated: true, searched_files: 2, skipped_entries: 1, hits: [{ id: 'code1', path: 'client.py', line: 4, snippet: malicious, snippet_truncated: true, snippet_start_column: 5, file_sha256: 'a'.repeat(64) }] },
    knowledge: { query: 'name', truncated: true, hits: [{ source_id: 'doc1', document_id: 'doc', provider: 'demo', api_version: 'v2', document_type: 'guide', source_ref: 'javascript:alert(1)', start_char: 0, end_char: 20, snippet: malicious, score: 0.5 }] },
  },
};
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('renders real source metadata and safely focuses citation evidence', async () => {
  const user = userEvent.setup(); HTMLElement.prototype.scrollIntoView = vi.fn();
  render(<ReportDetails analysis={saved} />);
  expect(screen.getByText('Partial evidence')).toBeTruthy();
  expect(screen.getByText('Source unavailable')).toBeTruthy();
  expect(screen.getByText('Some code or matching lines were omitted by search limits.')).toBeTruthy();
  await user.click(screen.getAllByRole('button', { name: 'Source 2: Code' })[0]);
  expect(document.activeElement).toBe(screen.getByRole('article', { name: 'Source 2: Code' }));
  expect(screen.getByText('Source 3: javascript:alert(1)')).toBeTruthy();
  expect(document.querySelector('img')).toBeNull();
  expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
  expect(screen.getAllByText(malicious).length).toBeGreaterThan(1);
});
it('distinguishes unavailable evidence from successful empty results', () => {
  const view = render(<ReportDetails analysis={{ ...saved, report: { ...saved.report, code: null, knowledge: null, affected_files: [], model_observations: [] } }} />);
  expect(screen.getByText('Documentation retrieval was unavailable.')).toBeTruthy();
  expect(screen.getByText('Code evidence was unavailable or no repository was selected.')).toBeTruthy();
  view.rerender(<ReportDetails analysis={{ ...saved, report: { ...saved.report, code: { ...saved.report.code!, hits: [] }, knowledge: { ...saved.report.knowledge!, hits: [] }, affected_files: [] } }} />);
  expect(screen.getByText('No exact matches were found in the searched files.')).toBeTruthy();
  expect(screen.getByText('No documentation matched the query and version filters.')).toBeTruthy();
});
it('loads saved evidence, retries failures and paginates history', async () => {
  const user = userEvent.setup(); let fails = true;
  const fetch = vi.fn(async (url: unknown) => {
    if (!String(url).includes('?')) { if (fails) { fails = false; return json({}, 503); } return json(saved); }
    return json(String(url).includes('offset=20') ? [] : Array.from({ length: 20 }, (_, i) => ({ ...saved, id: `run${i}` })));
  }); vi.stubGlobal('fetch', fetch);
  render(<ReportWorkspace project={project} initialId="run1" openComparison={vi.fn()} />);
  await screen.findByRole('alert'); await user.click(screen.getByRole('button', { name: 'Retry report' }));
  await screen.findByRole('heading', { name: 'Impact summary' });
  await user.click(screen.getByRole('button', { name: 'Next analyses' }));
  await screen.findByText('No saved analyses');
  expect(fetch.mock.calls.some(([url]) => String(url).includes('offset=20'))).toBe(true);
});
it('aborts and ignores stale report loads after switching project', async () => {
  let resolve!: (response: Response) => void;
  const fetch = vi.fn((url: unknown, _init?: RequestInit) => String(url).endsWith('/run1') ? new Promise<Response>(done => { resolve = done; }) : Promise.resolve(json([])));
  vi.stubGlobal('fetch', fetch);
  const view = render(<ReportWorkspace key="p1" project={project} initialId="run1" openComparison={vi.fn()} />);
  view.rerender(<ReportWorkspace key="p2" project={{ ...project, id: 'p2' }} initialId={null} openComparison={vi.fn()} />);
  expect(fetch.mock.calls.find(([url]) => String(url).endsWith('/run1'))![1]?.signal?.aborted).toBe(true);
  resolve(json(saved));
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Impact summary' })).toBeNull());
  expect(screen.getByText('Select a saved analysis')).toBeTruthy();
});
