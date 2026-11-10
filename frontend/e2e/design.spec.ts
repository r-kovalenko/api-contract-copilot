import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/projects?*', route => route.fulfill({ json: [] }));
});

test('design previews are labelled and navigation preserves project form state', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Project name', { exact: true }).fill('Keep my draft');
  await page.getByRole('button', { name: 'Comparison Preview' }).click();
  await expect(page.getByText('Design preview', { exact: true })).toBeVisible();
  await expect(page.getByRole('main')).toBeFocused();
  await expect(page.getByRole('heading', { name: 'See what changes.' })).toBeVisible();
  await page.getByRole('button', { name: /Optional locale field added/ }).click();
  await expect(page.getByRole('heading', { name: 'Optional locale field added' })).toBeVisible();
  await page.getByRole('button', { name: 'View sample impact report' }).click();
  await expect(page.getByRole('heading', { name: 'Evidence gaps' })).toBeVisible();
  await page.getByRole('button', { name: 'Back to workspace' }).click();
  await expect(page.getByLabel('Project name', { exact: true })).toHaveValue('Keep my draft');
});

test('screens fit desktop and mobile and expose keyboard navigation', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const [label, file] of [['Projects', 'projects'], ['Contracts', 'contracts'], ['Comparison Preview', 'comparison'], ['Impact report Preview', 'report'], ['Components Preview', 'components']]) {
      await page.getByRole('button', { name: label, exact: true }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
      await page.screenshot({ path: `test-results/design-${file}-${width}.png`, fullPage: true });
    }
  }
});
