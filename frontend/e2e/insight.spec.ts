import { expect, test, type Page } from '@playwright/test';

/**
 * Phase 3–4 slice of the PRD §16 acceptance scenario: the AI drafts but never applies on
 * its own, the weekly review applies decisions, analytics explain themselves, wellness
 * records state, and notifications reach the bell.
 * The stack runs the scripted demo provider (AI_PROVIDER=fake) — no network.
 */
async function register(page: Page) {
  await page.goto('/register');
  await page.getByLabel('Имя').fill('Insight');
  await page
    .getByLabel('Email')
    .fill(`ins-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@lifeos.test`);
  await page.getByLabel('Пароль').fill('E2e-Test-Passw0rd');
  await page.getByLabel('Часовой пояс').selectOption('Asia/Bishkek');
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Insight');
}

test('assistant: consent, draft, edit, confirm, undo', async ({ page }) => {
  await register(page);
  await page.goto('/assistant');
  await page.getByRole('button', { name: 'Включить ассистента' }).click();
  await expect(page.getByText(/AI может читать:/)).toBeVisible();
  await page.getByRole('button', { name: 'Новый разговор' }).first().click();
  await page.getByLabel(/Напишите сообщение/).fill('Добавь задачу: купить билеты домой');
  await page.keyboard.press('Enter');

  const card = page.locator('[data-status="PROPOSED"]').first();
  await expect(card).toBeVisible();
  await expect(card.getByText('Срок не указан — без срока.')).toBeVisible();
  await card.getByLabel('Название').fill('Купить билеты в Ош');
  await card.getByRole('button', { name: 'Подтвердить' }).click();

  const done = page.locator('[data-status="EXECUTED"]').first();
  await expect(done).toBeVisible();
  await page.goto('/tasks');
  await expect(page.getByRole('button', { name: /Купить билеты в Ош/ })).toBeVisible();

  await page.goBack();
  await page
    .locator('[data-status="EXECUTED"]')
    .first()
    .getByRole('button', { name: 'Отменить действие' })
    .click();
  await expect(page.locator('[data-status="REVERTED"]').first()).toBeVisible();
  await page.goto('/tasks');
  await expect(page.getByRole('button', { name: /Купить билеты в Ош/ })).toHaveCount(0);
});

test('weekly review applies task decisions', async ({ page }) => {
  await register(page);
  await page.goto('/tasks?view=today');
  await expect(page.getByText('На сегодня ничего')).toBeVisible();
  await page.getByLabel('Новая задача').fill('Старый хвост');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: /Старый хвост/ })).toBeVisible();

  await page.goto('/reviews');
  await page.getByRole('button', { name: 'Обзор этой недели' }).click();
  await expect(page.getByRole('heading', { name: 'Итоги недели' })).toBeVisible();
  await page.getByRole('button', { name: 'Дальше' }).click();
  const row = page.getByRole('listitem').filter({ hasText: 'Старый хвост' });
  await row.getByRole('radio', { name: 'Отменить' }).click();
  await page.getByRole('button', { name: 'Сохранить решения' }).click();
  await expect(page.getByRole('button', { name: 'Сохранено' })).toBeVisible();
  await page.getByRole('button', { name: 'Дальше' }).click();
  await page.getByLabel('Что получилось').fill('Закрыл старые задачи');
  await page.getByRole('radio', { name: '8' }).click();
  await page.getByRole('button', { name: 'Сохранить' }).click();
  await page.getByRole('button', { name: 'Дальше' }).click();
  await page.getByRole('button', { name: 'Завершить обзор' }).click();
  await expect(page.getByText(/Завершён/).first()).toBeVisible();

  await page.goto('/tasks?view=done');
  await expect(page.getByRole('button', { name: /Старый хвост/ })).toBeVisible();
});

test('analytics, wellness and the notification bell', async ({ page }) => {
  await register(page);
  await page.goto('/analytics/week');
  await expect(page.getByText('Выполнение задач')).toBeVisible();
  await expect(page.getByText('Нет данных').first()).toBeVisible();
  await page.getByText('Как считается').first().click();
  await expect(
    page.getByText(/Отменённые и задачи со сроком в будущем не учитываются/),
  ).toBeVisible();

  await page.goto('/wellness');
  const form = page.getByRole('region', { name: 'Как вы сейчас?' });
  await form
    .getByRole('radiogroup', { name: 'Настроение' })
    .getByRole('radio', { name: '7' })
    .click();
  await form.getByRole('radiogroup', { name: 'Энергия' }).getByRole('radio', { name: '6' }).click();
  await form.getByRole('button', { name: 'Отметить' }).click();
  await expect(page.getByText('Настроение 7 · Энергия 6')).toBeVisible();

  // A goal at 100% notifies the user instead of completing itself (BR-045).
  await page.goto('/goals');
  await page.getByRole('button', { name: 'Цель', exact: true }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Новая цель' });
  await dialog.getByLabel('Название').fill('Прочитать 3 книги');
  await dialog.getByRole('radio', { name: 'Вручную' }).click();
  await dialog.getByRole('button', { name: 'Сохранить' }).click();
  await page.getByLabel('Прогресс, %').fill('100');
  await page.getByRole('button', { name: 'Обновить' }).click();
  await expect(page.getByText('Цель достигнута!')).toBeVisible();
  await page.reload();
  const bell = page.getByRole('button', { name: /Уведомления: непрочитанных 1/ }).first();
  await expect(bell).toBeVisible();
  await bell.click();
  await expect(page.getByText(/«Прочитать 3 книги» достигла 100%/)).toBeVisible();
});
