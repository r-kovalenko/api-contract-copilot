import { useEffect, useRef, useState, type FormEvent } from 'react';
import { listContracts, uploadContract, validateFile, type Contract } from './contracts';
import { type Project } from './projects';
import { Badge, Button, EmptyState, Feedback, PageHeader, Panel } from './ui';

// The parent keys this workspace by project ID: drafts, requests and selections never cross projects.
export function Contracts({ project }: { project: Project }) {
  const [versions, setVersions] = useState<Contract[]>([]);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [version, setVersion] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [baseline, setBaseline] = useState('');
  const [candidate, setCandidate] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);
  const upload = useRef<AbortController | null>(null);
  useEffect(() => () => upload.current?.abort(), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    listContracts(project.id, offset, controller.signal).then(data => {
      if (controller.signal.aborted) return;
      setVersions(current => offset === 0 ? data : [...current, ...data.filter(item => !current.some(old => old.id === item.id))]);
      setMore(data.length === 20 && offset < 100000);
    }).catch(cause => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Versions could not be loaded.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [project.id, offset, revision]);

  function refresh() {
    setBaseline(''); setCandidate(''); setOffset(0); setRevision(value => value + 1);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (upload.current || !file || !version.trim()) return;
    const controller = new AbortController();
    upload.current = controller;
    setSaving(true); setUploadError(''); setNotice('');
    try {
      const saved = await uploadContract(project.id, version, file, controller.signal);
      if (controller.signal.aborted) return;
      setNotice(`Saved ${saved.version}. This contract version is immutable.`);
      setVersion(''); setFile(null);
      if (fileInput.current) fileInput.current.value = '';
      refresh();
    } catch (cause) {
      if (!controller.signal.aborted) setUploadError(cause instanceof Error && cause.name !== 'TimeoutError' && cause.name !== 'TypeError'
        ? cause.message : 'Upload could not be confirmed. Refresh versions before retrying; the server may have saved it.');
    } finally {
      if (!controller.signal.aborted) setSaving(false);
      upload.current = null;
    }
  }
  const selectedBaseline = versions.find(item => item.id === baseline);
  const selectedCandidate = versions.find(item => item.id === candidate);
  const validPair = !!selectedBaseline && !!selectedCandidate && baseline !== candidate && !loading && !error && !saving;
  const fileError = file ? validateFile(file) : '';
  return <>
    <PageHeader eyebrow={`${project.name} / CONTRACTS`} title="Give your change a baseline." action={<Badge tone="success">Contracts · Live feature</Badge>}>Upload two OpenAPI versions, then choose the current and proposed contracts.</PageHeader>
    <div className="two-column">
      <Panel aria-labelledby="upload-title"><h2 id="upload-title">Upload a contract</h2>
        <p>JSON or YAML · OpenAPI 3.0–3.2 · Maximum 1 MiB</p>
        <form onSubmit={submit}>
          <label htmlFor="contract-version">Version label</label>
          <input id="contract-version" required maxLength={100} value={version} disabled={saving} onChange={event => setVersion(event.target.value)} placeholder="v1" />
          <label htmlFor="contract-file">OpenAPI file</label>
          <input ref={fileInput} id="contract-file" type="file" required accept=".json,.yaml,.yml" disabled={saving} aria-describedby="file-help" onChange={event => { setFile(event.target.files?.[0] ?? null); setUploadError(''); setNotice(''); }} />
          <p id="file-help" className="field-hint">Each version label is unique within this project. Saved versions cannot be overwritten.</p>
          {fileError && <Feedback tone="error">{fileError}</Feedback>}
          <Button type="submit" disabled={saving || !file || !!fileError || !version.trim()}>{saving ? 'Validating and saving…' : 'Upload contract'}</Button>
          {uploadError && <Feedback tone="error">{uploadError}</Feedback>}
          {notice && <Feedback tone="success">{notice}</Feedback>}
        </form>
      </Panel>
      <Panel aria-labelledby="versions-title" aria-busy={loading}><div className="panel-heading"><h2 id="versions-title">Saved versions</h2><Button variant="quiet" disabled={loading || saving} onClick={refresh}>Refresh versions</Button></div>
        {loading && <Feedback>Loading versions…</Feedback>}
        {error && <><Feedback tone="error">{error}</Feedback><Button variant="secondary" onClick={() => setRevision(value => value + 1)}>Retry versions</Button></>}
        {!loading && !error && versions.length === 0 && <EmptyState title="No contracts yet">Upload your baseline to get started.</EmptyState>}
        <ul className="contract-versions">{versions.map(item => <li key={item.id}><strong>{item.version}</strong><Badge>OpenAPI {item.openapi_version}</Badge><p>{item.source_name || 'Unnamed source'} · <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></p></li>)}</ul>
        {more && <Button variant="secondary" disabled={loading || !!error || saving} onClick={() => setOffset(value => value + 20)}>Load more versions</Button>}
      </Panel>
    </div>
    <Panel className="contract-pair" aria-labelledby="pair-title"><h2 id="pair-title">Choose versions</h2><div className="two-column">
      {[{ id: 'baseline', title: 'Baseline version', value: baseline, set: setBaseline }, { id: 'candidate', title: 'Candidate version', value: candidate, set: setCandidate }].map(item => <div key={item.id}>
        <label htmlFor={item.id}>{item.title}</label><select id={item.id} value={item.value} disabled={loading || !!error || saving} onChange={event => item.set(event.target.value)}><option value="">Select a version</option>{versions.map(contract => <option key={contract.id} value={contract.id}>{contract.version} · {contract.source_name || 'Unnamed source'}</option>)}</select>
      </div>)}
    </div>
    <Feedback>{baseline && baseline === candidate ? 'Choose two different versions.' : validPair ? `${selectedBaseline.version} → ${selectedCandidate.version} · Version pair ready.` : 'Select a baseline and a different candidate from this project.'}</Feedback>
    <div className="action-bar"><p id="comparison-help">Comparison execution is coming in the next milestone. Your selection stays available while you navigate this workspace.</p><Button disabled aria-describedby="comparison-help">Compare contracts (coming soon)</Button></div>
    </Panel>
  </>;
}
