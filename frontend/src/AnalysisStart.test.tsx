// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AnalysisStart } from './AnalysisStart';
const props = { projectId: 'p1', comparisonId: 'c1', changeId: 'a'.repeat(64) };
const receipt = { id: 'run1', project_id: 'p1', comparison_id: 'c1', change_id: props.changeId, created_at: '2026-01-01', report: { status: 'partial', summary: '<img src=x> potential impact', model_status: 'offline', evidence_gaps: ['missing_code'] } };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Exact code search term'), 'full_name');
  await user.type(screen.getByLabelText('Documentation search terms'), 'customer migration');
}
it('submits the selected stable IDs once and confirms escaped partial results', async () => {
  const user = userEvent.setup(); let resolve!: (response: Response) => void;
  const fetch = vi.fn(() => new Promise<Response>(done => { resolve = done; })); vi.stubGlobal('fetch', fetch);
  render(<AnalysisStart {...props} />);
  expect((screen.getByRole('button', { name: 'Analyze impact' }) as HTMLButtonElement).disabled).toBe(true);
  await fill(user); await user.type(screen.getByLabelText('Repository alias (optional)'), 'consumer');
  await user.dblClick(screen.getByRole('button', { name: 'Analyze impact' }));
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe('/api/projects/p1/analyses');
  expect(JSON.parse(init.body as string)).toEqual({ comparison_id: 'c1', change_id: props.changeId, code_query: 'full_name', knowledge_query: 'customer migration', repository: 'consumer' });
  expect((screen.getByLabelText('Exact code search term') as HTMLInputElement).closest('fieldset')?.disabled).toBe(true);
  resolve(json(receipt, 201));
  await screen.findByText('Analysis saved.');
  expect(screen.getByText('Saved with evidence gaps')).toBeTruthy();
  expect(document.querySelector('img')).toBeNull();
});
it('retains inputs for validation errors and never retries automatically', async () => {
  const user = userEvent.setup(); const fetch = vi.fn().mockResolvedValue(json({}, 422)); vi.stubGlobal('fetch', fetch);
  render(<AnalysisStart {...props} />); await fill(user);
  await user.click(screen.getByRole('button', { name: 'Analyze impact' }));
  await screen.findByRole('alert');
  expect((screen.getByLabelText('Exact code search term') as HTMLInputElement).value).toBe('full_name');
  expect(fetch).toHaveBeenCalledTimes(1);
});
it('checks and reopens saved runs after uncertain POST without reposting', async () => {
  const user = userEvent.setup();
  const fetch = vi.fn(async (url: unknown, init?: RequestInit) => {
    if (init?.method === 'POST') throw new TypeError('network error');
    return json(String(url).includes('?') ? [receipt, { ...receipt, id: 'other', change_id: 'b'.repeat(64) }] : receipt);
  }); vi.stubGlobal('fetch', fetch);
  render(<AnalysisStart {...props} />); await fill(user);
  await user.click(screen.getByRole('button', { name: 'Analyze impact' })); await screen.findByRole('alert');
  expect((screen.getByRole('button', { name: 'Analyze impact' }) as HTMLButtonElement).disabled).toBe(true);
  await user.click(screen.getByRole('button', { name: 'Check saved analyses' }));
  await user.click(await screen.findByRole('button', { name: /Open saved run/ }));
  await screen.findByText('Analysis saved.');
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
});
it('aborts and ignores a late result when project or selected change changes', async () => {
  const user = userEvent.setup(); let resolve!: (response: Response) => void;
  const fetch = vi.fn((_url: unknown, _init?: RequestInit) => new Promise<Response>(done => { resolve = done; })); vi.stubGlobal('fetch', fetch);
  const view = render(<AnalysisStart key="first" {...props} />); await fill(user);
  await user.click(screen.getByRole('button', { name: 'Analyze impact' }));
  view.rerender(<AnalysisStart key="second" {...props} projectId="p2" changeId={'b'.repeat(64)} />);
  expect(fetch.mock.calls[0][1]?.signal?.aborted).toBe(true);
  resolve(json(receipt));
  await waitFor(() => expect(screen.queryByText('Analysis saved.')).toBeNull());
  expect((screen.getByLabelText('Exact code search term') as HTMLInputElement).value).toBe('');
});
