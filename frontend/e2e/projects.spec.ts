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
