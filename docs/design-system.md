# Product design checkpoint

The repository contains the editable design source: React screens, shared components and CSS tokens. No Figma file or external font service is required.

## Screen map

| Screen | Purpose | Current behavior |
| --- | --- | --- |
| Projects | Create an integration workspace and select a saved project | Live project API and PostgreSQL persistence |
| Contracts | Establish baseline and candidate versions | Live JSON/YAML upload, saved metadata, project-scoped version selectors |
| Comparison | Browse severity, operation and before/after detail | Interactive fixed Customer API v1 → v2 sample; no oasdiff call |
| Impact report | Review impact, code evidence, sources, gaps and migration steps | Clearly illustrative report; no search, retrieval or model call |
| Components | Review reusable component variants | Visual library, including empty, error, disabled and success states |

The preview screens do not mark future backlog features complete. They show the intended UI for Steps 2–4 so it can be reviewed before backend integration. Project form and selection state survive navigation within the current page. Reload behavior remains as documented in the MVP guide.

## Foundations

`frontend/src/tokens.css` defines semantic colors, typography, spacing and corner radii. The visual direction uses a dark navigation rail, light working surfaces, blue actions, compact typography and monospace contract evidence. No externally hosted assets are required.

Use the semantic colors for their defined roles: blue for action/selection, green for compatible/success, amber for warning/review and red for breaking/error. Always pair color with a text label. Do not describe incomplete or unverified evidence as confirmed.

The screen grids collapse on smaller viewports. Navigation becomes a wrapping row below 850px; forms and reports become a single column on narrow phones. Controls retain visible focus outlines, native keyboard behavior and labels. A skip link targets the main region. Screen changes focus that region; the project form retains its unsaved values.

## Component API

| Component | Variants / responsibilities |
| --- | --- |
| `Button` | primary, secondary, quiet; native disabled/type/ARIA props; defaults to `type="button"` |
| `Badge` | neutral, info, success, warning, danger; visible textual status |
| `Panel` | bordered surface with native section attributes; label via heading ID where needed |
| `PageHeader` | breadcrumb-style eyebrow, heading, summary and optional action/status |
| `Feedback` | info/success status messages or error alerts |
| `EmptyState` | short title, explanatory copy and decorative mark |
| `Shell` | navigation, active screen, workspace identity and main content region |

Fields currently use shared native input/select/textarea styles and explicit labels. Prefer native semantics over custom widgets. All untrusted strings render through React text nodes; do not add raw HTML for contracts, snippets or model output.

## Review locally

```sh
cd frontend
npm ci
npm run dev
```

Open the Vite URL and use the sidebar. Preview screens work without a database; Projects shows a recoverable error if the backend is unavailable. For real project creation, start the backend and PostgreSQL using the README instructions.

```sh
npm test
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e -- e2e/design.spec.ts
```

Design browser tests fake only the project list. They verify sample navigation, keyboard focus, draft retention and overflow at 1440px/390px, and capture all five screens. The full-stack tests exercise project creation, contract uploads, duplicate/invalid documents, persisted version selection, project isolation and responsive screenshots against PostgreSQL in CI. Screenshots are retained in the browser-test-results artifact for visual review. This is not a complete accessibility audit.
