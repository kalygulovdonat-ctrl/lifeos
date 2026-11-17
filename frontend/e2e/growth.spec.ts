import { expect, test, type Page } from '@playwright/test';

/**
 * Phase 2 slice of the PRD §16 acceptance scenario:
 * create and check off a habit, a goal moved by its milestones and tasks, a daily reflection,
 * and a timer that survives a reload.
 */
async function register(page: Page) {
  await page.goto('/register');
  await page.getByLabel('Имя').fill('Grower');
  await page
    .getByLabel('Email')
    .fill(`grow-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@lifeos.test`);
  await page.getByLabel('Пароль').fill('E2e-Test-Passw0rd');
  await page.getByLabel('Часовой пояс').selectOption('Asia/Bishkek');
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Grower');
}

test('habits: create, check off, quantity adds up, stats', async ({ page }) => {
  await register(page);
  await page.goto('/habits');
  await page.getByRole('button', { name: 'Привычка', exact: true }).first().click();
  let dialog = page.getByRole('dialog', { name: 'Новая привычка' });
  await dialog.getByLabel('Название').fill('Читать 20 минут');
  await dialog.getByRole('button', { name: 'Сохранить' }).click();
  await expect(dialog).toBeHidden();

  const read = page.getByRole('listitem').filter({ hasText: 'Читать 20 минут' });
  await read.getByRole('checkbox').click();
  await expect(page.getByText('1/1')).toBeVisible();

  await page.getByRole('button', { name: 'Привычка', exact: true }).first().click();
  dialog = page.getByRole('dialog', { name: 'Новая привычка' });
  await dialog.getByLabel('Название').fill('Вода');
  await dialog.getByRole('radio', { name: 'Количество' }).click();
  await dialog.getByLabel('Единица').fill('стаканов');
  await dialog.getByLabel(/Цель на день/).fill('8');
  await dialog.getByRole('button', { name: 'Сохранить' }).click();
  await expect(dialog).toBeHidden();

  const water = page.getByRole('listitem').filter({ hasText: 'Вода' });
  for (const [v, total] of [
    ['5', '5 / 8'],
    ['3', '8 / 8'],
  ] as const) {
    await water.getByLabel('Добавить значение для «Вода»').fill(v);
    await water.getByRole('button', { name: 'Добавить' }).click();
    await expect(water.getByText(new RegExp(total))).toBeVisible();
  }
  await expect(water.getByText(/8 \/ 8 стаканов/)).toBeVisible();
  await expect(page.getByText('2/2')).toBeVisible();

  await read.getByRole('link', { name: 'Читать 20 минут' }).click();
  await expect(page.getByRole('heading', { name: 'Читать 20 минут' })).toBeVisible();
  await expect(page.getByText('Последние полгода')).toBeVisible();
  await expect(page.getByRole('listitem').filter({ hasText: 'Выполнено' })).toHaveCount(1);
});

test('goals: milestones drive progress, completion needs confirmation', async ({ page }) => {
  await register(page);
  await page.goto('/goals');
  await page.getByRole('button', { name: 'Цель', exact: true }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Новая цель' });
  await dialog.getByLabel('Название').fill('Выучить английский');
  await dialog.getByRole('button', { name: 'Сохранить' }).click();
  await expect(page.getByRole('heading', { name: 'Выучить английский' })).toBeVisible();

  for (const title of ['A2', 'B1']) {
    await page.getByPlaceholder('Новый этап').fill(title);
    await page.getByRole('button', { name: 'Добавить' }).click();
    await expect(page.getByText(title, { exact: true })).toBeVisible();
  }
  await page
    .getByRole('listitem')
    .filter({ hasText: 'A2' })
    .getByRole('button', { name: 'Этап выполнен' })
    .click();
  await expect(page.getByText('50%').first()).toBeVisible();
  await page
    .getByRole('listitem')
    .filter({ hasText: 'B1' })
    .getByRole('button', { name: 'Этап выполнен' })
    .click();
  await expect(page.getByText('Цель достигнута!')).toBeVisible();
  await page.getByRole('button', { name: 'Завершить цель' }).first().click();
  await expect(page.getByText('Цель достигнута!')).toBeHidden();
  await page.getByRole('link', { name: 'Все цели' }).click();
  await expect(page.getByRole('link', { name: /Выучить английский/ })).toContainText('Завершена');
});

test('journal: daily reflection is saved and found', async ({ page }) => {
  await register(page);
  await page.goto('/journal');
  await page.getByRole('link', { name: /Подвести итоги дня/ }).click();
  await page.getByLabel('Что произошло сегодня?').fill('Сдал лабораторную по физике');
  await page.getByLabel('За что я благодарен?').fill('Друзьям за помощь');
  await page.getByRole('button', { name: 'Сохранить' }).click();
  await expect(page.getByRole('button', { name: 'Сохранено' })).toBeVisible();

  await page.getByRole('link', { name: 'Дневник', exact: true }).first().click();
  await page.getByLabel('Поиск по дневнику').fill('лабораторную');
  await expect(
    page.getByRole('link', { name: /Итоги дня/ }).filter({ hasText: 'Сдал лабораторную' }),
  ).toBeVisible();
});

test('time: timer survives reload and lands in the entries', async ({ page }) => {
  await register(page);
  await page.goto('/time');
  await page.getByLabel('Над чем работаете?').fill('Курсовая');
  await page.getByRole('button', { name: 'Старт' }).click();
  await expect(page.getByRole('button', { name: 'Пауза' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('link', { name: /Идёт таймер/ }).first()).toBeVisible();
  await expect(page.getByText('Курсовая').first()).toBeVisible();

  await page.getByRole('button', { name: 'Пауза' }).click();
  await expect(page.getByRole('button', { name: 'Продолжить' })).toBeVisible();
  await page.getByRole('button', { name: 'Стоп' }).click();
  await expect(page.getByRole('button', { name: 'Старт' })).toBeVisible();
  await expect(page.getByRole('listitem').filter({ hasText: 'Курсовая' })).toBeVisible();
});
