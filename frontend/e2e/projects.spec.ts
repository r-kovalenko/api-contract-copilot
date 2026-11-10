import { test, expect } from '@playwright/test';

test('create, reload and select a persisted project', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('No projects yet. Create your first project to begin.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create project', exact: true })).toBeDisabled();
  await page.getByLabel('Project name', { exact: true }).fill('Customer API migration');
  await page.getByLabel('Description').fill('<script>alert("synthetic")</script>');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByText('Created Customer API migration. Your project is saved.')).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: /Customer API migration/ }).click();
  await expect(page.getByRole('heading', { name: 'Customer API migration' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Customer API migration' })).toContainText('<script>alert("synthetic")</script>');
  await expect(page.locator('script:not([src])')).toHaveCount(0);
  await page.screenshot({ path: 'test-results/project-workspace.png', fullPage: true });
});

test('load failure can be retried and failed saves preserve input', async ({ page }) => {
  await page.route('**/api/projects?*', route => route.fulfill({ status: 503, body: '{}' }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Projects could not be loaded');
  await page.unroute('**/api/projects?*');
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Your projects' })).toHaveAttribute('aria-busy', 'false');
  await page.route('**/api/projects', route => route.fulfill({ status: 503, body: '{}' }));
  await page.getByLabel('Project name', { exact: true }).fill('Retain my draft');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Project could not be saved');
  await expect(page.getByLabel('Project name', { exact: true })).toHaveValue('Retain my draft');
});

test('upload JSON and YAML, reject duplicates, reload and choose project-scoped versions', async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto('/');
  await page.getByLabel('Project name', { exact: true }).fill('Upload walkthrough');
  await page.getByRole('button', { name: 'Create project', exact: true }).click();
  await page.getByRole('button', { name: 'Manage contracts' }).click();
  await expect(page.getByText('No contracts yet')).toBeVisible();
  for (const [version, file] of [['v1', 'customer-v1.json'], ['v2', 'customer-v2.yaml']]) {
    await page.getByLabel('Version label', { exact: true }).fill(version);
    await page.getByLabel('OpenAPI file').setInputFiles(`../docs/examples/${file}`);
    await page.getByRole('button', { name: 'Upload contract', exact: true }).click();
    await expect(page.getByText(`Saved ${version}. This contract version is immutable.`)).toBeVisible({ timeout: 15_000 });
  }
  await page.getByLabel('Version label', { exact: true }).fill('v1');
  await page.getByLabel('OpenAPI file').setInputFiles('../docs/examples/customer-v1.json');
  await page.getByRole('button', { name: 'Upload contract', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('already exists', { timeout: 15_000 });
  await page.getByLabel('Version label', { exact: true }).fill('bad');
  await page.getByLabel('OpenAPI file').setInputFiles({ name: 'invalid.json', mimeType: 'application/json', buffer: Buffer.from('{}') });
  await page.getByRole('button', { name: 'Upload contract', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Validation failed', { timeout: 15_000 });
  await page.reload();
  await page.getByRole('button', { name: /Upload walkthrough/ }).click();
  await page.getByRole('button', { name: 'Manage contracts' }).click();
  await expect(page.getByRole('region', { name: 'Saved versions' }).getByRole('listitem')).toHaveCount(2);
  await page.getByLabel('Baseline version').selectOption({ label: 'v1 · customer-v1.json' });
  await page.getByLabel('Candidate version').selectOption({ label: 'v1 · customer-v1.json' });
  await expect(page.getByText('Choose two different versions.')).toBeVisible();
  await page.getByLabel('Candidate version').selectOption({ label: 'v2 · customer-v2.yaml' });
  await expect(page.getByText('v1 → v2 · Version pair ready.')).toBeVisible();
  await expect(page.getByRole('button', { name: /Compare contracts/ })).toBeDisabled();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: `test-results/contracts-live-${width}.png`, fullPage: true });
  }
  await page.getByRole('button', { name: 'Projects', exact: true }).click();
  await page.getByRole('button', { name: /Customer API migration/ }).click();
  await page.getByRole('button', { name: 'Manage contracts' }).click();
  await expect(page.getByText('No contracts yet')).toBeVisible();
  await expect(page.getByLabel('Baseline version')).toHaveValue('');
  await expect(page.getByLabel('Candidate version')).toHaveValue('');
});
