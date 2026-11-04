export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export async function listProjects(offset: number, signal: AbortSignal): Promise<Project[]> {
  const response = await fetch(`/api/projects?offset=${offset}&limit=20`, { signal });
  if (!response.ok) throw new Error('Projects could not be loaded.');
  return response.json();
}

export async function createProject(name: string, description: string): Promise<Project> {
  const response = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description: description || null }),
  });
  if (!response.ok) {
    throw new Error(response.status === 422 || response.status === 413
      ? 'Check your project name (1–200 characters) and description (up to 2,000 characters).'
      : 'Project could not be saved. Check the project list before retrying.');
  }
  return response.json();
}
