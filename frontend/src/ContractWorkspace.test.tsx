// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Contracts } from './ContractWorkspace';
import { App } from './App';

const project = { id: 'p1', name: 'First project', description: null, created_at: '2026-01-01T00:00:00Z' };
const versions = ['v1', 'v2'].map(version => ({ id: version, project_id: 'p1', version, openapi_version: '3.1.0', source_name: 'api.json', created_at: project.created_at }));
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('uploads a file, refreshes metadata and selects only a distinct pair', async () => {
  const user = userEvent.setup(); let saved = false;
  const fetch = vi.fn(async (_url: unknown, init?: RequestInit) => {
    if (init?.method === 'POST') { saved = true; return json(versions[1], 201); }
    return json(saved ? versions : [versions[0]]);
  });
  vi.stubGlobal('fetch', fetch); render(<Contracts project={project} />);
  await screen.findByText('v1');
  await user.type(screen.getByLabelText('Version label'), 'v2');
  await user.upload(screen.getByLabelText('OpenAPI file'), new File(['{}'], 'api.yaml'));
  const submit = screen.getByRole('button', { name: 'Upload contract' }) as HTMLButtonElement;
  expect(submit.disabled).toBe(false);
  // jsdom does not reconcile user-event's FileList with native required-file validation.
  // The real-browser walkthrough submits through a click.
  fireEvent.submit(submit.closest('form')!);
  await screen.findByText('Saved v2. This contract version is immutable.');
  await screen.findByText('v2');
  await user.selectOptions(screen.getByLabelText('Baseline version'), 'v1');
  await user.selectOptions(screen.getByLabelText('Candidate version'), 'v1');
  expect(screen.getByText('Choose two different versions.')).toBeTruthy();
  expect((screen.getByRole('button', { name: /Compare contracts/ }) as HTMLButtonElement).disabled).toBe(true);
  await user.selectOptions(screen.getByLabelText('Candidate version'), 'v2');
  expect(screen.getByText('v1 → v2 · Version pair ready.')).toBeTruthy();
  expect((screen.getByRole('button', { name: /Compare contracts/ }) as HTMLButtonElement).disabled).toBe(true);
});

it.each([409, 422])('retains a rejected upload and safely renders validation (%s)', async status => {
  const user = userEvent.setup();
  vi.stubGlobal('fetch', vi.fn(async (_url: unknown, init?: RequestInit) => init?.method === 'POST'
    ? json({ detail: { code: 'invalid', message: '<img src=x onerror=alert(1)>' } }, status) : json([])));
  render(<Contracts project={project} />); await screen.findByText('No contracts yet');
  await user.type(screen.getByLabelText('Version label'), 'v1');
  await user.upload(screen.getByLabelText('OpenAPI file'), new File(['{}'], 'api.json'));
  const submit = screen.getByRole('button', { name: 'Upload contract' }) as HTMLButtonElement;
  expect(submit.disabled).toBe(false);
  // jsdom does not reconcile user-event's FileList with native required-file validation.
  // The real-browser walkthrough submits through a click.
  fireEvent.submit(submit.closest('form')!);
  const alert = await screen.findByRole('alert');
  expect(alert.textContent).toContain(status === 409 ? 'already exists' : 'Validation failed');
  expect(alert.querySelector('img')).toBeNull();
  expect((screen.getByLabelText('Version label') as HTMLInputElement).value).toBe('v1');
  expect((screen.getByLabelText('OpenAPI file') as HTMLInputElement).files?.length).toBe(1);
});

it('retries a failed list and loads older versions', async () => {
  const user = userEvent.setup();
  const first = Array.from({ length: 20 }, (_, i) => ({ ...versions[0], id: `id-${i}`, version: `version-${i}` }));
  const fetch = vi.fn().mockResolvedValueOnce(json({}, 503)).mockResolvedValueOnce(json(first)).mockResolvedValueOnce(json([versions[1]]));
  vi.stubGlobal('fetch', fetch); render(<Contracts project={project} />);
  await screen.findByRole('alert');
  await user.click(screen.getByRole('button', { name: 'Retry versions' }));
  await screen.findByText('version-0');
  await user.click(screen.getByRole('button', { name: 'Load more versions' }));
  await screen.findByText('v2');
  expect(fetch.mock.calls[2][0]).toContain('offset=20');
  expect(screen.getByText('version-0')).toBeTruthy();
});

it('clears drafts and selection on project switching and ignores stale responses', async () => {
  const user = userEvent.setup(); let resolveOld!: (response: Response) => void;
  const fetch = vi.fn(async (url: string) => {
    if (url.startsWith('/api/projects?')) return json([project, { ...project, id: 'p2', name: 'Second project' }]);
    if (url.includes('/p1/')) return new Promise<Response>(resolve => { resolveOld = resolve; });
    return json([]);
  });
  vi.stubGlobal('fetch', fetch); render(<App />);
  await user.click(await screen.findByRole('button', { name: /First project/ }));
  await user.click(screen.getByRole('button', { name: 'Manage contracts' }));
  await user.type(screen.getByLabelText('Version label'), 'old draft');
  await user.click(screen.getByRole('button', { name: 'Projects' }));
  await user.click(screen.getByRole('button', { name: /Second project/ }));
  await user.click(screen.getByRole('button', { name: 'Manage contracts' }));
  await screen.findByText('No contracts yet');
  resolveOld(json(versions));
  await waitFor(() => expect((screen.getByLabelText('Version label') as HTMLInputElement).value).toBe(''));
  expect(screen.queryByText('v1')).toBeNull();
  expect((screen.getByLabelText('Baseline version') as HTMLSelectElement).value).toBe('');
  const oldCall = fetch.mock.calls.find(call => call[0].includes('/p1/'))!;
  expect((oldCall as unknown as [string, RequestInit])[1].signal?.aborted).toBe(true);
});

it('prevents duplicate uploads and aborts an upload when the project changes', async () => {
  const user = userEvent.setup();
  let resolveUpload!: (response: Response) => void;
  const fetch = vi.fn(async (_url: string, init?: RequestInit) => init?.method === 'POST'
    ? new Promise<Response>(resolve => { resolveUpload = resolve; }) : json([]));
  vi.stubGlobal('fetch', fetch);
  const view = render(<Contracts key="p1" project={project} />);
  await screen.findByText('No contracts yet');
  await user.type(screen.getByLabelText('Version label'), 'v1');
  await user.upload(screen.getByLabelText('OpenAPI file'), new File(['{}'], 'api.json'));
  const form = screen.getByRole('button', { name: 'Upload contract' }).closest('form')!;
  fireEvent.submit(form);
  fireEvent.submit(form);
  expect(fetch.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
  expect((screen.getByRole('button', { name: 'Validating and saving…' }) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<Contracts key="p2" project={{ ...project, id: 'p2' }} />);
  const request = fetch.mock.calls.find(call => call[1]?.method === 'POST')!;
  expect(request[1]?.signal?.aborted).toBe(true);
  resolveUpload(json(versions[0], 201));
  await screen.findByText('No contracts yet');
  expect(screen.queryByText(/Saved v1/)).toBeNull();
  expect((screen.getByLabelText('Version label') as HTMLInputElement).value).toBe('');
});
