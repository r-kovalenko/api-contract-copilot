// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './App';

const project = { id: 'project-1', name: 'Customer API', description: 'Synthetic integration', created_at: '2026-01-01T00:00:00Z' };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('creates a project through HTTP, refreshes the list and selects the saved project', async () => {
  const user = userEvent.setup();
  let saved = false;
  const fetch = vi.fn(async (_url: unknown, options?: RequestInit) => {
    if (options?.method === 'POST') { saved = true; return json(project, 201); }
    return json(saved ? [project] : []);
  });
  vi.stubGlobal('fetch', fetch);
  render(<App />);
  await screen.findByText('No projects yet. Create your first project to begin.');
  expect((screen.getByRole('button', { name: 'Create project' }) as HTMLButtonElement).disabled).toBe(true);
  await user.type(screen.getByLabelText('Project name'), '  Customer API  ');
  await user.type(screen.getByLabelText(/Description/), project.description);
  await user.click(screen.getByRole('button', { name: 'Create project' }));
  await screen.findByText('Created Customer API. Your project is saved.');
  expect(fetch).toHaveBeenCalledWith('/api/projects', expect.objectContaining({ method: 'POST', body: JSON.stringify({ name: project.name, description: project.description }) }));
  const choice = await screen.findByRole('button', { name: /Customer API/ });
  expect(choice.getAttribute('aria-pressed')).toBe('true');
  expect((screen.getByLabelText('Project name') as HTMLInputElement).value).toBe('');
  expect(within(screen.getByRole('region', { name: project.name })).getByText(project.description)).toBeTruthy();
});

it.each([422, 413, 503])('retains input and shows safe feedback for rejected creation (%s)', async status => {
  const user = userEvent.setup();
  vi.stubGlobal('fetch', vi.fn(async (_url: unknown, options?: RequestInit) => options?.method === 'POST'
    ? json({ detail: 'private server details' }, status) : json([])));
  render(<App />);
  await screen.findByText('No projects yet. Create your first project to begin.');
  await user.type(screen.getByLabelText('Project name'), 'Retry me');
  await user.type(screen.getByLabelText(/Description/), 'Keep this description');
  await user.click(screen.getByRole('button', { name: 'Create project' }));
  const alert = await screen.findByRole('alert');
  expect(alert.textContent).toContain(status === 503 ? 'Check the project list before retrying' : 'Check your project name');
  expect(screen.queryByText(/private server details/)).toBeNull();
  expect((screen.getByLabelText('Project name') as HTMLInputElement).value).toBe('Retry me');
  expect((screen.getByLabelText(/Description/) as HTMLTextAreaElement).value).toBe('Keep this description');
  expect(screen.queryByText('SELECTED PROJECT')).toBeNull();
});

it('retries a failed list and supports keyboard selection without interpreting markup', async () => {
  const user = userEvent.setup();
  const other = { ...project, id: 'project-2', name: '<img src=x onerror=alert(1)>' };
  const fetch = vi.fn().mockResolvedValueOnce(json({}, 503)).mockImplementation(async () => json([project, other]));
  vi.stubGlobal('fetch', fetch);
  render(<App />);
  await screen.findByRole('alert');
  await user.click(screen.getByRole('button', { name: 'Retry' }));
  const first = await screen.findByRole('button', { name: /Customer API/ });
  first.focus();
  await user.keyboard('{Enter}');
  expect(first.getAttribute('aria-pressed')).toBe('true');
  const second = screen.getByRole('button', { name: /<img src=x/ });
  second.focus();
  await user.keyboard(' ');
  expect(second.getAttribute('aria-pressed')).toBe('true');
  expect(first.getAttribute('aria-pressed')).toBe('false');
  expect(screen.getByRole('region', { name: other.name }).querySelector('img')).toBeNull();
  expect(screen.queryByRole('alert')).toBeNull();
});

it('shows loading and prevents duplicate creation while a save is pending', async () => {
  const user = userEvent.setup();
  let resolveList!: (response: Response) => void;
  let resolveSave!: (response: Response) => void;
  const fetch = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { resolveList = resolve; }))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { resolveSave = resolve; }))
    .mockImplementation(async () => json([project]));
  vi.stubGlobal('fetch', fetch);
  render(<App />);
  expect(screen.getByText('Loading projects…')).toBeTruthy();
  resolveList(json([]));
  await screen.findByText('No projects yet. Create your first project to begin.');
  await user.type(screen.getByLabelText('Project name'), project.name);
  await user.click(screen.getByRole('button', { name: 'Create project' }));
  const saving = screen.getByRole('button', { name: 'Saving…' }) as HTMLButtonElement;
  expect(saving.disabled).toBe(true);
  await user.click(saving);
  expect(fetch.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1);
  resolveSave(json(project, 201));
  await waitFor(() => expect(screen.queryByText('Saving…')).toBeNull());
  await screen.findByRole('button', { name: /Customer API/ });
});
