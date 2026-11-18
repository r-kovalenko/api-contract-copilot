export type Severity = 'breaking' | 'potentially_breaking' | 'non_breaking';
export interface Change {
  id: string; rule_id: string; severity: Severity; summary: string;
  operation: string; path: string; section: string;
  evidence: { text: string; baseSource?: Source | null; revisionSource?: Source | null };
}
interface Source { file: string; line: number; column: number }
export interface ComparisonSummary {
  id: string; project_id: string; baseline_id: string; candidate_id: string;
  engine_version: string; normalization_version: number; change_count: number; created_at: string;
}
export interface Comparison extends ComparisonSummary {
  result: { engine: string; baseline_sha256: string; candidate_sha256: string; changes: Change[] };
}
const path = (projectId: string) => `/api/projects/${encodeURIComponent(projectId)}/comparisons`;
async function request<T>(url: string, signal: AbortSignal, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(30_000)]),
    ...(body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    if (response.status === 404) throw new Error('Comparison or versions not found in this project. Refresh and choose again.');
    if (response.status === 422) throw new Error('Choose two different valid contract versions.');
    if (response.status === 504) throw new Error('Comparison timed out. Try again.');
    throw new Error('Comparison service is unavailable. Refresh saved comparisons before retrying.');
  }
  return response.json();
}
export const createComparison = (project: string, baseline: string, candidate: string, signal: AbortSignal) =>
  request<Comparison>(path(project), signal, { baseline_id: baseline, candidate_id: candidate });
export const listComparisons = (project: string, offset: number, signal: AbortSignal) =>
  request<ComparisonSummary[]>(`${path(project)}?offset=${offset}&limit=20`, signal);
export const getComparison = (project: string, id: string, signal: AbortSignal) =>
  request<Comparison>(`${path(project)}/${encodeURIComponent(id)}`, signal);
export const getChange = (project: string, comparison: string, change: string, signal: AbortSignal) =>
  request<Change>(`${path(project)}/${encodeURIComponent(comparison)}/changes/${encodeURIComponent(change)}`, signal);
export const comparisonError = (cause: unknown) => cause instanceof Error && !['TimeoutError', 'TypeError'].includes(cause.name)
  ? cause.message : 'Request could not be confirmed. Refresh saved comparisons; the server may have completed it.';
