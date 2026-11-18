// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ComparisonWorkspace } from './ComparisonWorkspace';
import { Contracts } from './ContractWorkspace';
import { type Comparison } from './comparisons';
const project = { id: 'p1', name: 'Synthetic', description: null, created_at: '2026-01-01' };
const changes = [
  { id: 'a'.repeat(64), rule_id: 'removed', severity: 'breaking' as const, summary: '<img src=x> removed', operation: 'GET', path: '/customers', section: 'responses', evidence: { text: 'Field removed', baseSource: { file: 'baseline.json', line: 12, column: 3 } } },
  { id: 'b'.repeat(64), rule_id: 'added', severity: 'non_breaking' as const, summary: 'Field added', operation: 'GET', path: '/customers', section: 'responses', evidence: { text: 'Field added' } },
];
const saved: Comparison = { id: 'c1', project_id: 'p1', baseline_id: 'v1', candidate_id: 'v2', engine_version: '1.37.0', normalization_version: 1, change_count: 2, created_at: '2026-01-01', result: { engine: 'oasdiff', baseline_sha256: 'hash1', candidate_sha256: 'hash2', changes } };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('filters changes and fetches the selected stable ID with escaped evidence', async () => {
  const user = userEvent.setup();
  const fetch = vi.fn(async (url: unknown) => json(String(url).includes('/changes/') ? changes[0] : [saved]));
  vi.stubGlobal('fetch', fetch);
  render(<ComparisonWorkspace project={project} latest={saved} openContracts={vi.fn()} />);
  await screen.findByText('Baseline v1 → Candidate v2');
  await user.selectOptions(screen.getByLabelText('Filter by severity'), 'breaking');
  expect(screen.queryByRole('button', { name: /Field added/ })).toBeNull();
  await user.click(screen.getByRole('button', { name: /<img src=x> removed/ }));
  await screen.findByText('baseline.json, line 12, column 3', { exact: false });
  expect(fetch.mock.calls.some(([url]) => String(url) === `/api/projects/p1/comparisons/c1/changes/${changes[0].id}`)).toBe(true);
  expect(document.querySelector('img')).toBeNull();
  await user.selectOptions(screen.getByLabelText('Filter by severity'), 'potentially_breaking');
  expect(screen.getByText('No matching changes')).toBeTruthy();
  expect(screen.queryByText('Field removed')).toBeNull();
});
it('shows an empty result, retries list failures and clears details on version changes', async () => {
  const user = userEvent.setup();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json({}, 503)).mockImplementation(async () => json([])));
  const view = render(<ComparisonWorkspace project={project} latest={saved} openContracts={vi.fn()} />);
  await screen.findByRole('alert'); await user.click(screen.getByRole('button', { name: 'Retry comparisons' }));
  await screen.findByText('No saved comparisons');
  view.rerender(<ComparisonWorkspace project={project} latest={{ ...saved, id: 'c2', candidate_id: 'v3', change_count: 0, result: { ...saved.result, changes: [] } }} openContracts={vi.fn()} />);
  await screen.findByText('No contract changes');
  expect(screen.queryByRole('button', { name: /removed/ })).toBeNull();
});
it('ignores stale selected-change responses after another comparison arrives', async () => {
  const user = userEvent.setup(); let resolve!: (response: Response) => void;
  vi.stubGlobal('fetch', vi.fn((url: unknown) => String(url).includes('/changes/') ? new Promise<Response>(done => { resolve = done; }) : Promise.resolve(json([]))));
  const view = render(<ComparisonWorkspace project={project} latest={saved} openContracts={vi.fn()} />);
  await user.click(screen.getByRole('button', { name: /removed/ }));
  view.rerender(<ComparisonWorkspace project={project} latest={{ ...saved, id: 'c2', result: { ...saved.result, changes: [] }, change_count: 0 }} openContracts={vi.fn()} />);
  resolve(json(changes[0]));
  await screen.findByText('No contract changes');
  await waitFor(() => expect(screen.queryByText('Field removed')).toBeNull());
});
it('posts the chosen pair once, retains selections after errors, then opens the saved result', async () => {
  const user = userEvent.setup(); const onCompared = vi.fn(); let attempt = 0;
  const fetch = vi.fn(async (_url: unknown, init?: RequestInit) => init?.method === 'POST'
    ? json(++attempt === 1 ? {} : saved, attempt === 1 ? 504 : 201)
    : json(['v1', 'v2'].map(id => ({ id, project_id: 'p1', version: id, openapi_version: '3.1.0', source_name: 'api.json', created_at: '2026-01-01' }))));
  vi.stubGlobal('fetch', fetch); render(<Contracts project={project} onCompared={onCompared} />);
  await screen.findByText('v1');
  await user.selectOptions(screen.getByLabelText('Baseline version'), 'v1');
  await user.selectOptions(screen.getByLabelText('Candidate version'), 'v2');
  await user.click(screen.getByRole('button', { name: 'Compare contracts' }));
  await screen.findByText('Comparison timed out. Try again.');
  expect((screen.getByLabelText('Baseline version') as HTMLSelectElement).value).toBe('v1');
  await user.click(screen.getByRole('button', { name: 'Compare contracts' }));
  await waitFor(() => expect(onCompared).toHaveBeenCalledWith(saved));
  const calls = fetch.mock.calls.filter(([, init]) => init?.method === 'POST');
  expect(calls).toHaveLength(2);
  expect(JSON.parse(calls[0][1]!.body as string)).toEqual({ baseline_id: 'v1', candidate_id: 'v2' });
});
it('retries selected evidence errors and paginates saved comparisons', async () => {
  const user = userEvent.setup(); let failed = false;
  const fetch = vi.fn(async (url: unknown) => {
    const path = String(url);
    if (path.includes('/changes/')) { if (!failed) { failed = true; return json({}, 503); } return json(changes[0]); }
    if (path.endsWith('/c1')) return json(saved);
    return json(path.includes('offset=20') ? [] : Array.from({ length: 20 }, (_, i) => ({ ...saved, id: `saved-${i}` })));
  });
  vi.stubGlobal('fetch', fetch); render(<ComparisonWorkspace project={project} latest={saved} openContracts={vi.fn()} />);
  await user.click(screen.getByRole('button', { name: /<img src=x> removed/ }));
  await screen.findByRole('alert');
  await user.click(screen.getByRole('button', { name: /<img src=x> removed/ }));
  await screen.findByText('Field removed');
  await user.click(screen.getByRole('button', { name: 'Next comparisons' }));
  await screen.findByText('No saved comparisons');
  expect(fetch.mock.calls.some(([url]) => String(url).includes('offset=20'))).toBe(true);
});
it('aborts a pending comparison and never opens it after project switch', async () => {
  const user = userEvent.setup(); const onCompared = vi.fn(); let resolve!: (response: Response) => void;
  const fetch = vi.fn(async (_url: unknown, init?: RequestInit) => init?.method === 'POST' ? new Promise<Response>(done => { resolve = done; }) : json(['v1', 'v2'].map(id => ({ id, project_id: 'p1', version: id, openapi_version: '3.1.0', source_name: 'api.json', created_at: '2026-01-01' }))));
  vi.stubGlobal('fetch', fetch); const view = render(<Contracts key="p1" project={project} onCompared={onCompared} />);
  await screen.findByText('v1');
  await user.selectOptions(screen.getByLabelText('Baseline version'), 'v1');
  await user.selectOptions(screen.getByLabelText('Candidate version'), 'v2');
  await user.dblClick(screen.getByRole('button', { name: 'Compare contracts' }));
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  expect((screen.getByLabelText('Candidate version') as HTMLSelectElement).disabled).toBe(true);
  view.rerender(<Contracts key="p2" project={{ ...project, id: 'p2' }} onCompared={onCompared} />);
  expect(fetch.mock.calls.find(([, init]) => init?.method === 'POST')![1]?.signal?.aborted).toBe(true);
  resolve(json(saved));
  await screen.findByText('v1');
  expect(onCompared).not.toHaveBeenCalled();
});
