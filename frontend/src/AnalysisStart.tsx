import { useEffect, useRef, useState, type FormEvent } from 'react';
import { AnalysisError, createAnalysis, getAnalysis, listAnalyses, type AnalysisReceipt, type AnalysisSummary } from './analyses';
import { Badge, Button, Feedback } from './ui';

// Mount with a project/comparison/change key: changing selection aborts and clears drafts/results.
export function AnalysisStart({ projectId, comparisonId, changeId, openReport }: { projectId: string; comparisonId: string; changeId: string; openReport?: (id: string) => void }) {
  const [code, setCode] = useState('');
  const [knowledge, setKnowledge] = useState('');
  const [repository, setRepository] = useState('');
  const [provider, setProvider] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const [receipt, setReceipt] = useState<AnalysisReceipt | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[] | null>(null);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  const validText = (text: string) => Boolean(text.trim()) && !/[\x00-\x1f\x7f]/.test(text);
  const valid = validText(code) && validText(knowledge) && (!provider || validText(provider)) && (!repository || /^[A-Za-z0-9_-]{1,64}$/.test(repository));
  function begin() {
    if (pending.current) return null;
    const controller = new AbortController(); pending.current = controller; setBusy(true); setError(''); return controller;
  }
  function finish(controller: AbortController) {
    if (!controller.signal.aborted) { pending.current = null; setBusy(false); }
  }
  function failed(cause: unknown) {
    setError(cause instanceof AnalysisError ? cause.message : 'Analysis is unavailable. Check saved analyses before trying again.');
    if (cause instanceof AnalysisError && cause.uncertain) setUncertain(true);
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!valid || uncertain || receipt) return;
    const controller = begin(); if (!controller) return;
    try {
      const saved = await createAnalysis(projectId, { comparison_id: comparisonId, change_id: changeId, code_query: code, knowledge_query: knowledge, ...(repository ? { repository } : {}), ...(provider ? { provider } : {}) }, controller.signal);
      if (!controller.signal.aborted) setReceipt(saved);
    } catch (cause) { if (!controller.signal.aborted) failed(cause); }
    finally { finish(controller); }
  }
  async function checkSaved() {
    const controller = begin(); if (!controller) return;
    try {
      const saved = await listAnalyses(projectId, controller.signal);
      if (!controller.signal.aborted) setHistory(saved.filter(item => item.comparison_id === comparisonId && item.change_id === changeId));
    } catch (cause) { if (!controller.signal.aborted) failed(cause); }
    finally { finish(controller); }
  }
  async function open(id: string) {
    const controller = begin(); if (!controller) return;
    try {
      const saved = await getAnalysis(projectId, id, controller.signal);
      if (!controller.signal.aborted) { setReceipt(saved); setUncertain(false); }
    } catch (cause) { if (!controller.signal.aborted) failed(cause); }
    finally { finish(controller); }
  }
  return <section aria-label="Start impact analysis" className="analysis-start">
    <h3>Analyze this change</h3>
    <p>Choose search terms relevant to this change. Documentation uses the candidate API version.</p>
    <form onSubmit={submit}>
      <fieldset disabled={busy || Boolean(receipt)}>
        <legend>Evidence search</legend>
        <label htmlFor="analysis-code">Exact code search term</label><input id="analysis-code" required maxLength={200} value={code} onChange={event => setCode(event.target.value)} />
        <label htmlFor="analysis-knowledge">Documentation search terms</label><input id="analysis-knowledge" required maxLength={200} value={knowledge} onChange={event => setKnowledge(event.target.value)} />
        <label htmlFor="analysis-repository">Repository alias (optional)</label><input id="analysis-repository" maxLength={64} pattern="[A-Za-z0-9_-]+" value={repository} onChange={event => setRepository(event.target.value)} aria-describedby="repository-hint" />
        <p id="repository-hint" className="field-hint">Use a repository connected to this project. Leave blank to continue with an explicit code-evidence gap.</p>
        <label htmlFor="analysis-provider">Documentation provider (optional)</label><input id="analysis-provider" maxLength={100} value={provider} onChange={event => setProvider(event.target.value)} />
      </fieldset>
      <Button type="submit" disabled={!valid || busy || uncertain || Boolean(receipt)}>{busy ? 'Working…' : 'Analyze impact'}</Button>
    </form>
    {busy && <Feedback>Gathering or loading evidence. This may take up to a minute.</Feedback>}
    {error && <Feedback tone="error">{error}</Feedback>}
    {uncertain && <p>A disconnected request may still finish on the server. Refresh saved analyses before choosing to run again.</p>}
    {receipt && <div aria-label="Saved analysis"><Feedback tone="success">Analysis saved.</Feedback><Badge tone={receipt.report.status === 'partial' ? 'warning' : 'success'}>{receipt.report.status === 'partial' ? 'Saved with evidence gaps' : 'Evidence ready'}</Badge><p>{receipt.report.summary}</p><p>{receipt.report.evidence_gaps.length} evidence gaps recorded. {receipt.report.model_status === 'offline' ? 'Offline provider: no model analysis was performed.' : 'Model observations remain separate from deterministic facts.'}</p><p className="field-hint">Saved run: <code>{receipt.id}</code>.</p>{openReport && <Button onClick={() => openReport(receipt.id)}>View impact report</Button>}</div>}
    <Button variant="secondary" disabled={busy} onClick={checkSaved}>Check saved analyses</Button>
    {history !== null && <div><p>Matching runs among the latest 20 project analyses. Older runs remain available through the API.</p>{history.length ? <ul>{history.map(item => <li key={item.id}><Button variant="quiet" disabled={busy} onClick={() => open(item.id)}>Open saved run {new Date(item.created_at).toLocaleString()}</Button></li>)}</ul> : <p>No matching saved runs in this page.</p>}{(uncertain || receipt) && <Button variant="secondary" disabled={busy} onClick={() => { setUncertain(false); setReceipt(null); setError(''); }}>Start a separate run</Button>}</div>}
  </section>;
}
