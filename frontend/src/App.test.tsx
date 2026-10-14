import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { App } from './App';

describe('starter application', () => {
  it('communicates the implementation status without promising working analysis', () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain('API Contract Copilot');
    expect(html).toContain('Contract upload and impact analysis are planned.');
    expect(html).toContain('https://github.com/r-kovalenko/api-contract-copilot/issues');
  });
});
