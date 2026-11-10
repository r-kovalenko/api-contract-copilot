export interface Contract {
  id: string;
  project_id: string;
  version: string;
  openapi_version: string;
  source_name: string | null;
  created_at: string;
}

export function validateFile(file: File): string {
  if (!file.size || file.size > 1024 * 1024) return 'Choose a nonempty file no larger than 1 MiB.';
  if (!/^[A-Za-z0-9][A-Za-z0-9._ -]*\.(json|ya?ml)$/.test(file.name) || file.name.includes('..') || file.name.length > 255)
    return 'Use a plain .json, .yaml or .yml filename starting with a letter or number, without paths or consecutive dots.';
  return '';
}

const path = (projectId: string) => `/api/projects/${encodeURIComponent(projectId)}/contracts`;

export async function listContracts(projectId: string, offset: number, signal: AbortSignal): Promise<Contract[]> {
  const response = await fetch(`${path(projectId)}?offset=${offset}&limit=20`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(15_000)]),
  });
  if (!response.ok) throw new Error(response.status === 404 ? 'Project no longer exists. Select another project.' : 'Versions could not be loaded. Try again.');
  return response.json();
}

export async function uploadContract(projectId: string, version: string, file: File, signal: AbortSignal): Promise<Contract> {
  const error = validateFile(file);
  if (error) throw new Error(error);
  const query = new URLSearchParams({ version: version.trim(), source_name: file.name });
  const response = await fetch(`${path(projectId)}?${query}`, {
    method: 'POST', body: file,
    headers: { 'Content-Type': file.name.endsWith('.json') ? 'application/json' : 'application/yaml' },
    signal: AbortSignal.any([signal, AbortSignal.timeout(30_000)]),
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error('This version already exists. Choose a new version label.');
    if (response.status === 413) throw new Error('The file exceeds the 1 MiB upload limit.');
    if (response.status === 404) throw new Error('Project no longer exists. Select another project.');
    if (response.status === 415) throw new Error('Upload an uncompressed OpenAPI JSON or YAML file.');
    if (response.status === 422) {
      const body = await response.json().catch(() => null);
      const detail: unknown = body?.detail;
      // Only display the validator's bounded message, never arbitrary server error bodies.
      if (detail && typeof detail === 'object' && 'code' in detail && 'message' in detail && typeof detail.message === 'string')
        throw new Error(`Validation failed: ${detail.message.slice(0, 400)}`);
      throw new Error('Validation failed. Check the OpenAPI document and version label (1–100 characters).');
    }
    throw new Error('Upload could not be confirmed. Refresh versions before retrying; the server may have saved it.');
  }
  return response.json();
}
