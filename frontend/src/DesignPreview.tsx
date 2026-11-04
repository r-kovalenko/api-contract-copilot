import { useState } from 'react';
import { Badge, Button, EmptyState, Feedback, PageHeader, Panel } from './ui';

export type Screen = 'projects' | 'contracts' | 'comparison' | 'report' | 'components';
const changes = [
  { id: 'customer-name', method: 'GET', path: '/customers/{id}', title: 'Customer name field renamed', detail: 'The response field full_name is removed and display_name is added. Consumers reading full_name need an explicit update.', before: 'full_name: string', after: 'display_name: string', severity: 'Breaking' },
  { id: 'customer-delete', method: 'DELETE', path: '/customers/{id}', title: 'Customer deletion endpoint removed', detail: 'The candidate contract no longer exposes this operation. Existing callers need an alternative workflow.', before: 'DELETE /customers/{id}', after: 'Operation removed', severity: 'Breaking' },
  { id: 'customer-locale', method: 'GET', path: '/customers/{id}', title: 'Optional locale field added', detail: 'An optional response field provides the customer locale. Existing consumers can ignore it.', before: 'No locale field', after: 'locale?: string', severity: 'Compatible' },
] as const;

export function DesignPreview({ screen, navigate }: { screen: Exclude<Screen, 'projects'>; navigate: (screen: Screen) => void }) {
  const [selected, setSelected] = useState(0);
  const [baseline, setBaseline] = useState('v1');
  const [candidate, setCandidate] = useState('v2');
  const change = changes[selected];
  return <>
    <div className="preview-banner"><Badge tone="warning">Design preview</Badge><span>Sample data · No files are uploaded and no analysis is executed.</span><Button variant="quiet" onClick={() => navigate('projects')}>Back to workspace</Button></div>
    {screen === 'contracts' && <>
      <PageHeader eyebrow="Customer API migration / Contracts" title="Give your change a baseline.">Choose the contract you use today and the version you want to adopt.</PageHeader>
      <div className="two-column">
        {[{ title: 'Baseline contract', value: baseline, set: setBaseline, label: 'Current integration', id: 'baseline' }, { title: 'Candidate contract', value: candidate, set: setCandidate, label: 'Proposed API version', id: 'candidate' }].map(item => <Panel key={item.id} aria-labelledby={`${item.id}-title`}>
          <p className="eyebrow">{item.label}</p><h2 id={`${item.id}-title`}>{item.title}</h2>
          <div className="upload-preview"><span className="file-symbol" aria-hidden="true">{'{ }'}</span><strong>OpenAPI contract</strong><p>JSON or YAML · OpenAPI 3.x</p><Badge>Upload planned</Badge></div>
          <label htmlFor={item.id}>Sample version</label><select id={item.id} value={item.value} onChange={event => item.set(event.target.value)}><option value="v1">v1 · Customer API</option>{item.id === 'candidate' && <option value="v2">v2 · Customer API</option>}</select>
          <p className="field-hint">This selector demonstrates the version-pair interaction.</p>
        </Panel>)}
      </div>
      <div className="action-bar"><p>{baseline === candidate ? 'Choose two different versions to continue.' : `${baseline} → ${candidate} · Sample comparison ready to explore`}</p><Button disabled={baseline === candidate} onClick={() => { setSelected(0); navigate('comparison'); }}>Explore sample comparison →</Button></div>
    </>}
    {screen === 'comparison' && <>
      <PageHeader eyebrow="Customer API migration / Comparison" title="See what changes.">A sample comparison of Customer API v1 → v2. Contract facts and interpretation have separate places.</PageHeader>
      <div className="summary-grid"><Panel><span className="metric">3</span><span>Sample changes</span></Panel><Panel><span className="metric danger-text">2</span><span>Breaking changes</span></Panel><Panel><span className="metric success-text">1</span><span>Compatible addition</span></Panel></div>
      <div className="comparison-grid"><Panel aria-labelledby="changes-title"><h2 id="changes-title">Contract changes</h2><div className="change-list">{changes.map((item, index) => <button key={item.id} className="change-option" aria-pressed={index === selected} onClick={() => setSelected(index)}><Badge tone={item.severity === 'Breaking' ? 'danger' : 'success'}>{item.severity}</Badge><strong>{item.title}</strong><code>{item.method} {item.path}</code></button>)}</div></Panel>
        <Panel aria-labelledby="change-title"><p className="eyebrow">CHANGE DETAIL</p><h2 id="change-title">{change.title}</h2><p>{change.detail}</p><div className="diff-block"><div><span>BASELINE · v1</span><code>− {change.before}</code></div><div><span>CANDIDATE · v2</span><code>+ {change.after}</code></div></div><p className="field-hint">Illustrative contract fact. Live comparisons will be produced by oasdiff.</p><Button onClick={() => navigate('report')}>View sample impact report →</Button><p className="field-hint">The sample report demonstrates the name-field change.</p></Panel></div>
    </>}
    {screen === 'report' && <>
      <PageHeader eyebrow="Customer API migration / Impact report" title="Turn a change into a plan." action={<Badge tone="warning">Sample report</Badge>}>Customer name field renamed · GET /customers/{'{id}'}</PageHeader>
      <div className="report-grid"><div className="stack"><Panel aria-labelledby="impact-title"><div className="panel-heading"><h2 id="impact-title">Impact summary</h2><Badge tone="danger">Breaking</Badge></div><p>The integration expects <code>full_name</code>. A v2 response supplies <code>display_name</code>, so the example customer label needs a mapping update.</p><Feedback>Evidence example only. No repository has been searched for this preview.</Feedback></Panel>
        <Panel aria-labelledby="files-title"><h2 id="files-title">Affected code</h2><p className="field-hint">Illustrative path and snippet; not a verified repository finding.</p><div className="code-evidence"><div><code>consumer/customer_client.py</code><Badge>Sample</Badge></div><pre><code>{'def customer_label(customer):\n    return customer["full_name"]'}</code></pre></div></Panel>
        <Panel aria-labelledby="plan-title"><h2 id="plan-title">Suggested migration</h2><ol className="plan-list"><li><strong>Update the response mapping</strong><p>Read display_name when using the v2 contract.</p></li><li><strong>Verify compatibility</strong><p>Test missing values and both supported API versions.</p></li><li><strong>Review before creating tasks</strong><p>Task creation will require explicit approval in a later milestone.</p></li></ol></Panel></div>
        <aside className="stack" aria-label="Report evidence"><Panel><h2>Sources</h2><div className="source-row"><Badge>Contract</Badge><strong>Customer API v1 → v2</strong><p>Sample response schema</p></div><div className="source-row"><Badge>Guide</Badge><strong>Customer API migration notes</strong><p>Illustrative source; no document retrieved</p></div></Panel><Panel><h2>Evidence gaps</h2><p>No live code search, retrieved documentation, or model output is connected yet.</p><Badge tone="warning">Verification needed</Badge></Panel><Button variant="secondary" onClick={() => navigate('comparison')}>← Back to comparison</Button></aside></div>
    </>}
    {screen === 'components' && <>
      <PageHeader eyebrow="Design system / Component library" title="One visual language.">Shared building blocks for the working application and the next MVP screens.</PageHeader>
      <div className="two-column"><Panel><h2>Actions</h2><div className="component-row"><Button>Primary action</Button><Button variant="secondary">Secondary</Button><Button variant="quiet">Quiet</Button><Button disabled>Unavailable</Button></div><p className="field-hint">Specimen buttons demonstrate appearance only.</p></Panel><Panel><h2>Status labels</h2><div className="component-row"><Badge>Draft</Badge><Badge tone="info">Selected</Badge><Badge tone="success">Compatible</Badge><Badge tone="warning">Needs review</Badge><Badge tone="danger">Breaking</Badge></div></Panel><Panel><h2>Feedback</h2><div className="stack"><Feedback>Loading and informative messages.</Feedback><Feedback tone="success">Your project has been saved.</Feedback><Feedback tone="error">Could not save. Your input is retained.</Feedback></div></Panel><Panel><h2>Empty state</h2><EmptyState title="No contracts yet">Add your first version to establish a baseline.</EmptyState></Panel><Panel><h2>Form fields</h2><label htmlFor="specimen-name">Project name</label><input id="specimen-name" placeholder="Customer API migration" /><p className="field-hint">A short, recognizable name for your integration.</p><label htmlFor="specimen-error">Version label</label><input id="specimen-error" defaultValue="v1" aria-invalid="true" aria-describedby="specimen-error-help" /><p id="specimen-error-help" className="danger-text">Example: this version already exists.</p></Panel><Panel><h2>Color tokens</h2><div className="swatches">{['accent', 'ink', 'surface', 'success', 'warning', 'danger'].map(color => <div key={color}><span className={`swatch swatch--${color}`} /><code>{color}</code></div>)}</div><p className="field-hint">Semantic colors always appear with a text label. Typography uses system sans-serif and monospace for code.</p></Panel></div>
    </>}
  </>;
}
