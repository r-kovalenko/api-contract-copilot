import { afterEach, expect, it, vi } from 'vitest';
import { uploadContract, validateFile, listContracts } from './contracts';

afterEach(() => vi.unstubAllGlobals());
const file = (name: string, size = 10) => ({ name, size } as File);
it.each(['../api.json', 'api..json', 'api.txt', 'api.JSON'])('rejects unsupported filenames: %s', name => {
  expect(validateFile(file(name))).not.toBe('');
});
it('bounds files before uploading', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  for (const size of [0, 1024 * 1024 + 1]) {
    await expect(uploadContract('p', 'v1', file('api.json', size), new AbortController().signal)).rejects.toThrow('1 MiB');
  }
  expect(fetch).not.toHaveBeenCalled();
  expect(validateFile(file('api.yaml', 1024 * 1024))).toBe('');
});
it.each([['api.json', 'application/json'], ['api.yml', 'application/yaml']])('sends raw %s with encoded metadata', async (name, media) => {
  const fetch = vi.fn().mockResolvedValue(new Response('{}')); vi.stubGlobal('fetch', fetch);
  const body = file(name);
  await uploadContract('project', ' v1 & v2 ', body, new AbortController().signal);
  expect(fetch).toHaveBeenCalledWith('/api/projects/project/contracts?version=v1+%26+v2&source_name='+name,
    expect.objectContaining({ body, method: 'POST', headers: { 'Content-Type': media } }));
});
it.each([[409, 'already exists'], [413, '1 MiB'], [415, 'uncompressed'], [422, 'Validation failed'], [503, 'Refresh versions']])('provides safe guidance for %s', async (status, message) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('private detail', { status: Number(status) })));
  await expect(uploadContract('p', 'v1', file('api.json'), new AbortController().signal)).rejects.toThrow(String(message));
});
it('scopes paginated reads and propagates caller cancellation', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('[]')); vi.stubGlobal('fetch', fetch);
  const controller = new AbortController();
  await listContracts('project', 20, controller.signal);
  controller.abort();
  expect(fetch.mock.calls[0][0]).toBe('/api/projects/project/contracts?offset=20&limit=20');
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});
