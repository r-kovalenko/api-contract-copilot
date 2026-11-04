import { afterEach, describe, expect, it, vi } from 'vitest';
import { createProject, listProjects } from './projects';

afterEach(() => vi.unstubAllGlobals());

describe('project API client', () => {
  it('uses same-origin JSON and preserves user text as data', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'test' })));
    vi.stubGlobal('fetch', fetch);
    await createProject('<script>example</script>', '');
    expect(fetch).toHaveBeenCalledWith('/api/projects', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ name: '<script>example</script>', description: null }),
    }));
  });
  it('shows validation guidance without reflecting raw server errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('private details', { status: 422 })));
    await expect(createProject('name', '')).rejects.toThrow('Check your project name');
  });
  it('fails visibly when storage is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })));
    await expect(listProjects(0, new AbortController().signal)).rejects.toThrow('could not be loaded');
    await expect(createProject('name', '')).rejects.toThrow('Check the project list before retrying');
  });
});
