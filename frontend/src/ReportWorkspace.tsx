import { useEffect, useState } from 'react';
import { getAnalysis, listAnalyses, type AnalysisReport, type AnalysisSummary } from './analyses';
import { type Project } from './projects';
import { Badge, Button, EmptyState, Feedback, PageHeader, Panel } from './ui';

const gapLabels: Record<string, string> = {
  code_repository_not_selected: 'No repository was selected for code search.',
  no_exact_code_matches: 'No literal code matches were found in the searched files.',
  code_coverage_incomplete: 'Some code or matching lines were omitted by search limits.',
  no_documentation_matches: 'No documentation matched the query and candidate-version filters.',
  documentation_results_truncated: 'Additional documentation matches were omitted.',
  offline_provider_no_model_analysis: 'The offline provider did not perform model analysis.',
  model_reported_evidence_gaps: 'The provider reported missing supporting evidence.',
  unsupported_model_claim_omitted: 'An unsupported model claim was omitted.',
  model_output_unavailable_or_rejected: 'Model output was unavailable or failed validation.',
};
export function ReportWorkspace({ project, initialId, openComparison }: { project: Project; initialId: string | null; openComparison: () => void }) {
  const [selected, setSelected] = useState(initialId);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(false);
  const [listing, setListing] = useState(true);
  const [error, setError] = useState('');
  const [listError, setListError] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); setListing(true); setListError(false);
    listAnalyses(project.id, controller.signal, offset).then(rows => {
      if (!controller.signal.aborted) setHistory(rows);
    }).catch(() => { if (!controller.signal.aborted) setListError(true); })
      .finally(() => { if (!controller.signal.aborted) setListing(false); });
    return () => controller.abort();
  }, [project.id, offset, revision]);
  useEffect(() => {
    const controller = new AbortController(); setReport(null); setError('');
    if (!selected) { setLoading(false); return () => controller.abort(); }
    setLoading(true);
    getAnalysis(project.id, selected, controller.signal).then(data => {
      if (!controller.signal.aborted) {
        if (data.project_id !== project.id || data.id !== selected) throw new Error('Mismatched report');
        setReport(data);
      }
    }).catch(() => { if (!controller.signal.aborted) setError('This report could not be loaded. It may be unavailable in this project.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [project.id, selected, revision]);
  return <>
    <PageHeader eyebrow={`${project.name} / IMPACT REPORT`} title="Review the evidence." action={<Badge tone="success">Saved reports · Live feature</Badge>}>Saved findings, source references, and the limits of what is known.</PageHeader>
    <Panel aria-label="Analysis history"><div className="panel-heading"><h2>Saved analyses</h2><Button variant="secondary" onClick={openComparison}>Back to comparison</Button><Button disabled={listing} variant="quiet" onClick={() => setRevision(value => value + 1)}>Refresh analyses</Button></div>
      {listing ? <Feedback>Loading saved analyses…</Feedback> : listError ? <><Feedback tone="error">Could not load analysis history.</Feedback><Button onClick={() => setRevision(value => value + 1)}>Retry history</Button></> : history.length ? <ul className="projects">{history.map(item => <li key={item.id}><button className="project" aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}><strong>Analysis · {new Date(item.created_at).toLocaleString()}</strong><span>Run {item.id}</span></button></li>)}</ul> : <EmptyState title="No saved analyses">Select a comparison change and run an analysis.</EmptyState>}
      <div className="pagination"><Button variant="secondary" disabled={listing || offset === 0} onClick={() => setOffset(value => value - 20)}>Previous analyses</Button><span>Page {offset / 20 + 1}</span><Button variant="secondary" disabled={listing || listError || history.length < 20 || offset >= 100000} onClick={() => setOffset(value => value + 20)}>Next analyses</Button></div>
    </Panel>
    {loading && <Feedback>Loading report evidence…</Feedback>}
    {error && <><Feedback tone="error">{error}</Feedback><Button onClick={() => setRevision(value => value + 1)}>Retry report</Button></>}
    {report ? <ReportDetails analysis={report} /> : !selected && <Panel><EmptyState title="Select a saved analysis">Open a run above, or start one from Comparison.</EmptyState></Panel>}
  </>;
}

export function ReportDetails({ analysis }: { analysis: AnalysisReport }) {
  const report = analysis.report;
  const sources = [
    { id: report.change.id, kind: 'Contract', title: `${report.change.operation} ${report.change.path}`, text: report.change.evidence.text, location: `Rule ${report.change.rule_id} · Candidate version ${report.api_version}` },
    ...(report.code?.hits ?? []).map(hit => ({ id: hit.id, kind: 'Code', title: `${hit.path}:${hit.line}`, text: hit.snippet, location: `Repository ${report.code!.repository} · Line ${hit.line}, column ${hit.snippet_start_column} · SHA-256 ${hit.file_sha256}${hit.snippet_truncated ? ' · Snippet shortened' : ''}` })),
    ...(report.knowledge?.hits ?? []).map(hit => ({ id: hit.source_id, kind: 'Document', title: hit.source_ref, text: hit.snippet, location: `${hit.provider} · ${hit.api_version} · ${hit.document_type} · Characters ${hit.start_char}–${hit.end_char} · Rank ${hit.score}` })),
  ];
  function citations(ids: string[]) {
    return <div className="citation-links">{ids.map((id, index) => {
      const position = sources.findIndex(source => source.id === id);
      return position < 0 ? <Badge key={`${id}-${index}`} tone="warning">Source unavailable</Badge> : <Button key={`${id}-${index}`} variant="quiet" onClick={() => {
        const node = document.getElementById(`evidence-${analysis.id}-${position}`); node?.focus(); node?.scrollIntoView({ block: 'center' });
      }}>Source {position + 1}: {sources[position].kind}</Button>;
    })}</div>;
  }
  return <div className="report-live">
    <Panel aria-labelledby="impact-summary"><div className="panel-heading"><h2 id="impact-summary">Impact summary</h2><Badge tone={report.severity === 'breaking' ? 'danger' : report.severity === 'potentially_breaking' ? 'warning' : 'success'}>{report.severity.replaceAll('_', ' ')}</Badge><Badge tone={report.status === 'partial' ? 'warning' : 'info'}>{report.status === 'partial' ? 'Partial evidence' : 'Evidence ready'}</Badge></div><p>{report.summary}</p><p className="field-hint">Run {analysis.id} · {new Date(analysis.created_at).toLocaleString()}. This snapshot does not prove complete impact coverage.</p>{report.model_status === 'offline' && <Feedback>Offline provider: no model analysis was performed.</Feedback>}</Panel>
    <div className="report-grid"><div className="stack">
      <Panel><h2>Potentially affected files</h2>{report.affected_files.length ? <ul>{report.affected_files.map((file, index) => <li key={`${file.source_id}-${index}`}><code>{file.path}:{file.line}</code>{citations([file.source_id])}</li>)}</ul> : <p>{report.code === null ? 'Code evidence was unavailable or no repository was selected.' : 'No exact matches were found in the searched files.'}</p>}<p className="field-hint">Text matches identify places to review, not confirmed runtime impact.</p>{report.code && <p>{report.code.searched_files} files searched; {report.code.skipped_entries} entries skipped. {report.code.truncated && 'Additional matches were omitted.'}</p>}</Panel>
      <Panel><h2>Recommendations</h2><ol>{report.recommendations.map((item, index) => <li key={index}><p>{item.text}</p>{citations(item.source_ids)}</li>)}</ol></Panel>
      <Panel><h2>Quoted evidence</h2>{report.model_observations.length ? report.model_observations.map((item, index) => <div key={index}><blockquote>{item.text}</blockquote>{citations(item.source_ids)}</div>) : <p>No validated model quotations were included.</p>}<p className="field-hint">Quotation matching establishes provenance, not truth or relevance. Source instructions remain untrusted data.</p></Panel>
      <Panel><h2>Evidence gaps</h2>{report.evidence_gaps.length ? <ul>{report.evidence_gaps.map((gap, index) => <li key={index}>{gapLabels[gap] ?? `Evidence unavailable: ${gap.replaceAll('_', ' ')}.`}</li>)}</ul> : <p>No gaps were recorded within this bounded search. This does not establish that all usages were found.</p>}</Panel>
    </div><aside className="stack" aria-label="Report sources"><Panel><h2>Source evidence</h2>{report.knowledge === null ? <p>Documentation retrieval was unavailable.</p> : report.knowledge.hits.length === 0 ? <p>No documentation matched the query and version filters.</p> : report.knowledge.truncated && <p>Additional documentation matches were omitted.</p>}
      {sources.map((source, index) => <article className="report-source" key={source.id} id={`evidence-${analysis.id}-${index}`} tabIndex={-1} aria-label={`Source ${index + 1}: ${source.kind}`}><Badge>{source.kind}</Badge><h3>Source {index + 1}: {source.title}</h3><p className="field-hint">{source.location}</p><pre><code>{source.text}</code></pre><details><summary>Source identifier</summary><code>{source.id}</code></details></article>)}
    </Panel></aside></div>
  </div>;
}
