import { defineConfig, devices } from '@playwright/test';

/**
 * E2E runs against a running stack (CI starts docker compose; locally: `make up`).
 * Base URL can be overridden with E2E_BASE_URL.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    // The UI picks its language from the browser; specs assert the default (Russian) UI.
    locale: 'ru-RU',
    timezoneId: 'Asia/Bishkek',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
