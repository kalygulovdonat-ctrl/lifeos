import { expect, test } from '@playwright/test';

/**
 * Phase 0 slice of the PRD §16 acceptance scenario:
 * register (profile, time zone, language) → reload keeps the session → change language →
 * sign out → session is gone.
 */
test('register, survive reload, switch language, sign out', async ({ page }) => {
  const email = `e2e-${Date.now()}@lifeos.test`;
  const password = 'E2e-Test-Passw0rd';

  await page.goto('/register');
  await page.getByLabel('Имя').fill('E2E');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Пароль').fill(password);
  await page.getByLabel('Часовой пояс').selectOption('Asia/Bishkek');
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();

  await expect(page.getByRole('heading', { level: 1 })).toContainText('E2E');
  await expect(page.getByText('Часовой пояс: Asia/Bishkek')).toBeVisible();

  // NFR-010: the in-memory access token is restored from the HttpOnly refresh cookie.
  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('E2E');
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  expect(await page.evaluate(() => document.cookie)).not.toContain('lifeos_refresh');

  await page.getByRole('link', { name: 'Настройки' }).click();
  await page.getByLabel('Язык', { exact: true }).selectOption('ky');
  await page.getByRole('button', { name: 'Сохранить' }).click();
  await expect(page.getByRole('heading', { name: 'Жөндөөлөр' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'ky');

  await page.getByRole('button', { name: 'Чыгуу' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});

test('protected routes redirect anonymous users to login', async ({ page }) => {
  await page.goto('/settings/profile');
  await expect(page).toHaveURL(/\/login$/);
});
