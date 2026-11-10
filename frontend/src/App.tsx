import { useEffect, useState, type FormEvent } from 'react';
import { createProject, listProjects, type Project } from './projects';
import { DesignPreview, type Screen } from './DesignPreview';
import { Contracts } from './ContractWorkspace';
import { Shell } from './Shell';
import { Badge, Button, EmptyState, Feedback, PageHeader, Panel } from './ui';

export function App() {
  const [selected, setSelected] = useState<Project | null>(null);
  const [contractsVisited, setContractsVisited] = useState(false);
  const [screen, setScreen] = useState<Screen>('projects');
  function navigate(next: Screen) {
    setScreen(next);
    if (next === 'contracts') setContractsVisited(true);
    requestAnimationFrame(() => document.getElementById('workspace-main')?.focus());
  }
  return <Shell screen={screen} navigate={navigate}>
    <div hidden={screen !== 'projects'}><ProjectWorkspace selected={selected} setSelected={setSelected} openContracts={() => navigate('contracts')} /></div>
    {selected && contractsVisited ? <div hidden={screen !== 'contracts'}><Contracts key={selected.id} project={selected} /></div> : screen === 'contracts' && <Panel><EmptyState title="Select a project first">Choose or create a project to upload its contracts.</EmptyState><Button onClick={() => navigate('projects')}>Choose a project</Button></Panel>}
    {screen !== 'projects' && screen !== 'contracts' && <DesignPreview screen={screen} navigate={navigate} />}
  </Shell>;
}

function ProjectWorkspace({ selected, setSelected, openContracts }: { selected: Project | null; setSelected: (project: Project) => void; openContracts: () => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [notice, setNotice] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    listProjects(offset, controller.signal).then(data => {
      if (!controller.signal.aborted) setProjects(data);
    }).catch(() => {
      if (!controller.signal.aborted) setError('Projects could not be loaded. Check that the backend and database are running.');
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [offset, revision]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving || !name.trim()) return;
    setSaving(true);
    setSaveError('');
    setNotice('');
    try {
      const project = await createProject(name.trim(), description.trim());
      setSelected(project);
      setName('');
      setDescription('');
      setOffset(0);
      setRevision(value => value + 1);
      setNotice(`Created ${project.name}. Your project is saved.`);
    } catch (cause) {
      setSaveError(cause instanceof Error ? cause.message : 'Project could not be saved.');
    } finally {
      setSaving(false);
    }
  }

  return <>
    <PageHeader eyebrow="WORKSPACE / PROJECTS" title="Your next migration starts here." action={<Badge tone="success">Projects · Live feature</Badge>}>Organize your API contracts and keep each integration’s changes in one place.</PageHeader>
    <div className="journey"><span className="journey-current">01 <strong>Create a project</strong></span><span>02 Add contracts</span><span>03 Compare changes</span><span>04 Explore impact</span></div>
    <div className="workspace">
      <Panel aria-labelledby="create-title">
        <p className="eyebrow">STEP 1</p>
        <h2 id="create-title">Create a project</h2>
        <form onSubmit={submit}>
          <label htmlFor="project-name">Project name</label>
          <input id="project-name" required maxLength={200} value={name} onChange={event => setName(event.target.value)} placeholder="Customer API migration" />
          <label htmlFor="project-description">Description <span className="muted">(optional)</span></label>
          <textarea id="project-description" maxLength={2000} rows={4} value={description} onChange={event => setDescription(event.target.value)} placeholder="What integration are you investigating?" />
          <Button type="submit" disabled={saving || !name.trim()}>{saving ? 'Saving…' : 'Create project'}</Button>
          {saveError && <Feedback tone="error">{saveError}</Feedback>}
          {notice && <Feedback tone="success">{notice}</Feedback>}
        </form>
      </Panel>
      <Panel aria-labelledby="projects-title" aria-busy={loading}>
        <h2 id="projects-title">Your projects</h2>
        {loading ? <Feedback>Loading projects…</Feedback> : error ? <>
          <Feedback tone="error">{error}</Feedback><Button variant="secondary" onClick={() => setRevision(value => value + 1)}>Retry</Button>
        </> : <>
          {projects.length === 0 ? <EmptyState title={offset === 0 ? 'Make room for your next change' : 'You’re all caught up'}>{offset === 0 ? 'No projects yet. Create your first project to begin.' : 'No more projects.'}</EmptyState> :
            <ul className="projects">{projects.map(project => <li key={project.id}>
              <button className="project" aria-pressed={selected?.id === project.id} onClick={() => setSelected(project)}>
                <strong>{project.name}</strong><span>{project.description || 'No description'}</span>
              </button>
            </li>)}</ul>}
          <div className="pagination">
            <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous</Button>
            <span>Page {offset / 20 + 1}</span>
            <Button variant="secondary" disabled={projects.length < 20} onClick={() => setOffset(value => value + 20)}>Next</Button>
          </div>
        </>}
      </Panel>
    </div>
    {selected && <Panel aria-labelledby="selected-title" className="selected">
      <p className="eyebrow">SELECTED PROJECT</p>
      <h2 id="selected-title">{selected.name}</h2>
      <p>{selected.description || 'Ready for your API contracts.'}</p>
      <p>Upload your baseline and candidate OpenAPI versions for this project.</p><Button onClick={openContracts}>Manage contracts</Button>
    </Panel>}
  </>;
}
