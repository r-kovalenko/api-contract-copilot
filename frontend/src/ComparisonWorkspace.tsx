import { useEffect, useRef, useState } from 'react';
import { AnalysisStart } from './AnalysisStart';
import { comparisonError, getChange, getComparison, listComparisons, type Change, type Comparison, type ComparisonSummary, type Severity } from './comparisons';
import { type Project } from './projects';
import { Badge, Button, EmptyState, Feedback, PageHeader, Panel } from './ui';
const labels: Record<Severity, string> = { breaking: 'Breaking', potentially_breaking: 'Potentially breaking', non_breaking: 'Nonbreaking' };
const tone = (severity: Severity) => severity === 'breaking' ? 'danger' as const : severity === 'potentially_breaking' ? 'warning' as const : 'success' as const;

export function ComparisonWorkspace({ project, latest, openContracts }: { project: Project; latest: Comparison | null; openContracts: () => void }) {
  const [saved, setSaved] = useState<ComparisonSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [comparison, setComparison] = useState<Comparison | null>(latest);
  const [selectedId, setSelectedId] = useState('');
  const [change, setChange] = useState<Change | null>(null);
  const [filter, setFilter] = useState<Severity | 'all'>('all');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  useEffect(() => {
    pending.current?.abort(); setComparison(latest); setChange(null); setSelectedId(''); setError(''); setBusy(false); setFilter('all'); setOffset(0);
  }, [latest]);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setListError('');
    listComparisons(project.id, offset, controller.signal).then(data => {
      if (!controller.signal.aborted) setSaved(data);
    }).catch(cause => { if (!controller.signal.aborted) setListError(comparisonError(cause)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [project.id, offset, revision, latest]);
  function begin() {
    pending.current?.abort(); const controller = new AbortController(); pending.current = controller;
    setBusy(true); setError(''); setChange(null); setSelectedId(''); return controller;
  }
  async function open(id: string) {
    const controller = begin(); setComparison(null); setFilter('all');
    try { const data = await getComparison(project.id, id, controller.signal); if (!controller.signal.aborted) setComparison(data); }
    catch (cause) { if (!controller.signal.aborted) setError(comparisonError(cause)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  async function select(id: string) {
    if (!comparison) return;
    const controller = begin(); setSelectedId(id);
    try { const data = await getChange(project.id, comparison.id, id, controller.signal); if (!controller.signal.aborted) setChange(data); }
    catch (cause) { if (!controller.signal.aborted) setError(comparisonError(cause)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  function filterBy(value: Severity | 'all') {
    pending.current?.abort(); setFilter(value); setChange(null); setSelectedId(''); setError(''); setBusy(false);
  }
  const visible = comparison?.result.changes.filter(item => filter === 'all' || item.severity === filter) ?? [];
  return <>
    <PageHeader eyebrow={`${project.name} / COMPARISON`} title="See what changes." action={<Badge tone="success">Comparison · Live feature</Badge>}>Deterministic contract changes with saved source evidence.</PageHeader>
    <Panel className="comparison-history" aria-labelledby="history-title"><div className="panel-heading"><h2 id="history-title">Saved comparisons</h2><Button variant="secondary" onClick={openContracts}>Choose versions</Button><Button variant="quiet" disabled={loading} onClick={() => setRevision(value => value + 1)}>Refresh comparisons</Button></div>
      {loading ? <Feedback>Loading comparisons…</Feedback> : listError ? <><Feedback tone="error">{listError}</Feedback><Button onClick={() => setRevision(value => value + 1)}>Retry comparisons</Button></> : <>
        {saved.length === 0 ? <EmptyState title="No saved comparisons">Choose two uploaded versions to compare.</EmptyState> : <ul className="projects">{saved.map(item => <li key={item.id}><button className="project" aria-pressed={comparison?.id === item.id} onClick={() => open(item.id)}><strong>{item.change_count} changes · {new Date(item.created_at).toLocaleString()}</strong><span>Baseline {item.baseline_id} → Candidate {item.candidate_id}</span></button></li>)}</ul>}
        <div className="pagination"><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(value => value - 20)}>Previous comparisons</Button><span>Page {offset / 20 + 1}</span><Button variant="secondary" disabled={saved.length < 20 || offset >= 100000} onClick={() => setOffset(value => value + 20)}>Next comparisons</Button></div>
      </>}
    </Panel>
    {busy && <Feedback>Loading evidence…</Feedback>}{error && <Feedback tone="error">{error} Select the comparison or change again to retry.</Feedback>}
    {comparison && <>
      <Panel className="comparison-provenance"><h2>Compared versions</h2><p>Baseline: <code>{comparison.baseline_id}</code></p><p>Candidate: <code>{comparison.candidate_id}</code></p><p>oasdiff {comparison.engine_version} · Normalization {comparison.normalization_version} · {comparison.change_count} changes</p><details><summary>Canonical document hashes</summary><p>Baseline: <code>{comparison.result.baseline_sha256}</code></p><p>Candidate: <code>{comparison.result.candidate_sha256}</code></p></details></Panel>
      <div className="comparison-grid"><Panel aria-labelledby="changes-title"><h2 id="changes-title">Contract changes</h2><label htmlFor="severity">Filter by severity</label><select id="severity" value={filter} onChange={event => filterBy(event.target.value as Severity | 'all')}><option value="all">All changes</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        {visible.length === 0 ? <EmptyState title={comparison.change_count === 0 ? 'No contract changes' : 'No matching changes'}>{comparison.change_count === 0 ? 'The engine found no changes between these versions.' : 'Choose another severity filter.'}</EmptyState> : <div className="change-list">{visible.map(item => <button className="change-option" key={item.id} aria-pressed={selectedId === item.id} onClick={() => select(item.id)}><Badge tone={tone(item.severity)}>{labels[item.severity]}</Badge><strong>{item.summary}</strong><code>{item.operation} {item.path}</code></button>)}</div>}
      </Panel><Panel className="comparison-provenance" aria-labelledby="detail-title"><h2 id="detail-title">Change evidence</h2>{change ? <><Badge tone={tone(change.severity)}>{labels[change.severity]}</Badge><h3>{change.summary}</h3><p>{change.evidence.text}</p><p><code>{change.operation} {change.path}</code> · {change.section}</p><p>Rule: <code>{change.rule_id}</code></p><p className="comparison-provenance">Stable change ID: <code>{change.id}</code></p>{(['baseSource', 'revisionSource'] as const).map((key, index) => <p key={key}><strong>{index === 0 ? 'Baseline' : 'Candidate'} evidence: </strong>{change.evidence[key] ? `${change.evidence[key].file}, line ${change.evidence[key].line}, column ${change.evidence[key].column}` : 'No source location supplied by the engine.'}</p>)}<p className="field-hint">Locations refer to canonical JSON engine inputs, not original uploaded file lines.</p><AnalysisStart key={`${project.id}:${comparison.id}:${change.id}`} projectId={project.id} comparisonId={comparison.id} changeId={change.id} /></> : <EmptyState title="Select a change">Inspect its saved engine evidence. No impact analysis has been run.</EmptyState>}</Panel></div>
    </>}
  </>;
}
