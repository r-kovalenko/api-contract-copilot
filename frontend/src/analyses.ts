import { type Change, type Severity } from './comparisons';
export interface AnalysisInput {
  comparison_id: string; change_id: string; code_query: string; knowledge_query: string;
  repository?: string; provider?: string;
}
export interface AnalysisSummary {
  id: string; project_id: string; comparison_id: string; change_id: string; created_at: string;
}
export interface AnalysisReceipt extends AnalysisSummary {
  report: { status: 'partial' | 'evidence_ready'; summary: string; model_status: string; evidence_gaps: string[] };
}
export interface AnalysisReport extends AnalysisReceipt {
  request: AnalysisInput;
  report: AnalysisReceipt['report'] & {
    severity: Severity; change: Change; api_version: string;
    affected_files: { path: string; line: number; source_id: string }[];
    recommendations: { text: string; source_ids: string[] }[];
    model_observations: { text: string; source_ids: string[] }[];
    code: null | { repository: string; query: string; truncated: boolean; searched_files: number; skipped_entries: number; hits: { id: string; path: string; line: number; snippet: string; snippet_truncated: boolean; snippet_start_column: number; file_sha256: string }[] };
    knowledge: null | { query: string; truncated: boolean; hits: { source_id: string; document_id: string; provider: string; api_version: string; document_type: string; source_ref: string; start_char: number; end_char: number; snippet: string; score: number }[] };
  };
}
export class AnalysisError extends Error {
  constructor(message: string, readonly uncertain = false) { super(message); }
}
const path = (project: string) => `/api/projects/${encodeURIComponent(project)}/analyses`;
async function request<T>(url: string, signal: AbortSignal, body?: AnalysisInput): Promise<T> {
  try {
    const response = await fetch(url, {
      signal: AbortSignal.any([signal, AbortSignal.timeout(60_000)]),
      ...(body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) {
      if (response.status === 404) throw new AnalysisError('The selected change or saved analysis is no longer available in this project.');
      if (response.status === 422) throw new AnalysisError('Check the search terms and configured repository alias.');
      throw new AnalysisError('The request could not be confirmed. Check saved analyses before starting another run.', Boolean(body));
    }
    return await response.json();
  } catch (cause) {
    if (cause instanceof AnalysisError) throw cause;
    throw new AnalysisError('The request could not be confirmed. Check saved analyses before starting another run.', Boolean(body));
  }
}
export const createAnalysis = (project: string, input: AnalysisInput, signal: AbortSignal) => request<AnalysisReceipt>(path(project), signal, input);
export const listAnalyses = (project: string, signal: AbortSignal, offset = 0) => request<AnalysisSummary[]>(`${path(project)}?limit=20&offset=${offset}`, signal);
export const getAnalysis = (project: string, id: string, signal: AbortSignal) => request<AnalysisReport>(`${path(project)}/${encodeURIComponent(id)}`, signal);
