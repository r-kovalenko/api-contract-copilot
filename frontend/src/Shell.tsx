import { type ReactNode } from 'react';
import { type Screen } from './DesignPreview';
import { Badge } from './ui';

export function Shell({ screen, navigate, children }: { screen: Screen; navigate: (screen: Screen) => void; children: ReactNode }) {
  const navigation: { id: Screen; label: string; mark: string }[] = [
    { id: 'projects', label: 'Projects', mark: '01' },
    { id: 'contracts', label: 'Contracts', mark: '02' },
    { id: 'comparison', label: 'Comparison', mark: '03' },
    { id: 'report', label: 'Impact report', mark: '04' },
    { id: 'components', label: 'Components', mark: '◇' },
  ];
  return <div className="app-shell">
    <a className="skip-link" href="#workspace-main">Skip to content</a>
    <aside className="sidebar">
      <a className="brand" href="#workspace-main" onClick={() => navigate('projects')}><span className="brand-mark" aria-hidden="true">{'{↗}'}</span><span>Contract<span className="brand-light">Copilot</span></span></a>
      <div className="workspace-label"><span className="workspace-avatar">L</span><div><strong>Local workspace</strong><small>API engineering</small></div></div>
      <p className="nav-label">WORKSPACE</p>
      <nav aria-label="Main navigation">{navigation.map(item => <button key={item.id} aria-label={`${item.label}${item.id === 'projects' ? '' : ' Preview'}`} aria-current={screen === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><span aria-hidden="true">{item.mark}</span>{item.label}{item.id !== 'projects' && <small>Preview</small>}</button>)}</nav>
      <div className="sidebar-note"><span className="status-dot" />Single-user preview<p>Understand the change.<br />Keep the evidence.</p></div>
    </aside>
    <div className="app-body"><div className="topbar"><span>API Contract Copilot</span><Badge tone="info">MVP · Design checkpoint</Badge></div>
      <main id="workspace-main" tabIndex={-1}>{children}</main>
      <footer>Local development workspace · Use synthetic data</footer>
    </div>
  </div>;
}
