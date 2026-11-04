import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { App } from './App';

describe('project workspace', () => {
  it('provides a labelled creation form and honest progress', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('Create a project');
    expect(html).toContain('for="project-name"');
    expect(html).toContain('for="project-description"');
    expect(html).toContain('Loading projects');
    expect(html).toContain('Main navigation');
    expect(html).toContain('Preview');
    expect(html).toContain('Skip to content');
  });
});
