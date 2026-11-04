import { useEffect, useState, type FormEvent } from 'react';
import { createProject, listProjects, type Project } from './projects';

export function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
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

  return <main>
    <header>
      <p className="eyebrow">API CONTRACT COPILOT · LOCAL WORKSPACE</p>
      <h1>Start with a project.</h1>
      <p>Give your API integration a home. Next, you’ll add two contract versions and explore what changed.</p>
    </header>
    <nav aria-label="MVP progress" className="steps">
      <span aria-current="step">1 · Project</span><span>2 · Contracts — next</span><span>3 · Compare — planned</span><span>4 · Impact — planned</span>
    </nav>
    <div className="workspace">
      <section aria-labelledby="create-title">
        <p className="eyebrow">STEP 1</p>
        <h2 id="create-title">Create a project</h2>
        <form onSubmit={submit}>
          <label htmlFor="project-name">Project name</label>
          <input id="project-name" required maxLength={200} value={name} onChange={event => setName(event.target.value)} placeholder="Customer API migration" />
          <label htmlFor="project-description">Description <span className="muted">(optional)</span></label>
          <textarea id="project-description" maxLength={2000} rows={4} value={description} onChange={event => setDescription(event.target.value)} placeholder="What integration are you investigating?" />
          <button type="submit" disabled={saving || !name.trim()}>{saving ? 'Saving…' : 'Create project'}</button>
          {saveError && <p role="alert">{saveError}</p>}
          <p role="status">{notice}</p>
        </form>
      </section>
      <section aria-labelledby="projects-title" aria-busy={loading}>
        <h2 id="projects-title">Your projects</h2>
        {loading ? <p role="status">Loading projects…</p> : error ? <>
          <p role="alert">{error}</p><button onClick={() => setRevision(value => value + 1)}>Retry</button>
        </> : <>
          {projects.length === 0 ? <p>{offset === 0 ? 'No projects yet. Create your first project to begin.' : 'No more projects.'}</p> :
            <ul className="projects">{projects.map(project => <li key={project.id}>
              <button className="project" aria-pressed={selected?.id === project.id} onClick={() => setSelected(project)}>
                <strong>{project.name}</strong><span>{project.description || 'No description'}</span>
              </button>
            </li>)}</ul>}
          <div className="pagination">
            <button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous</button>
            <span>Page {offset / 20 + 1}</span>
            <button disabled={projects.length < 20} onClick={() => setOffset(value => value + 20)}>Next</button>
          </div>
        </>}
      </section>
    </div>
    {selected && <section aria-labelledby="selected-title" className="selected">
      <p className="eyebrow">SELECTED PROJECT</p>
      <h2 id="selected-title">{selected.name}</h2>
      <p>{selected.description || 'Ready for your API contracts.'}</p>
      <p><strong>Up next:</strong> upload your baseline and candidate OpenAPI versions. Contract upload will be added in Step 2.</p>
    </section>}
    <footer>Single-user local preview · Projects are stored in PostgreSQL · Use synthetic data</footer>
  </main>;
}
