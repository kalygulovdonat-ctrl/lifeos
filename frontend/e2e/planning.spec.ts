import { expect, test, type Page } from '@playwright/test';

/**
 * Phase 1 slice of the PRD §16 acceptance scenario:
 * capture → triage → plan a task with subtasks → complete; events with conflicts and
 * free time; the dashboard reflects both.
 */
async function register(page: Page) {
  await page.goto('/register');
  await page.getByLabel('Имя').fill('Planner');
  await page.getByLabel('Email').fill(`plan-${Date.now()}@lifeos.test`);
  await page.getByLabel('Пароль').fill('E2e-Test-Passw0rd');
  await page.getByLabel('Часовой пояс').selectOption('Asia/Bishkek');
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Planner');
}

test('tasks: inbox capture, triage, subtasks, postpone, complete', async ({ page }) => {
  await register(page);

  await page.goto('/tasks/inbox');
  await page.getByLabel('Новая задача').fill('Идея для курсовой');
  await page.keyboard.press('Enter');
  const row = page.getByRole('listitem').filter({ hasText: 'Идея для курсовой' });
  await expect(row).toBeVisible();
  await row.getByRole('button', { name: 'Разобрано' }).click();
  await expect(page.getByText('Входящие разобраны')).toBeVisible();

  await page.getByRole('link', { name: 'Сегодня', exact: true }).click();
  await expect(page).toHaveURL(/view=today/);
  await expect(page.getByText('На сегодня ничего')).toBeVisible();
  await page.getByLabel('Новая задача').fill('Сдать лабораторную');
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: /Сдать лабораторную/ }).click();

  const drawer = page.getByRole('dialog', { name: 'Задача' });
  await expect(drawer).toBeVisible();
  for (const title of ['Собрать данные', 'Написать вывод']) {
    await drawer.getByPlaceholder('Добавить подзадачу и нажать Enter').fill(title);
    await page.keyboard.press('Enter');
    await expect(drawer.getByText(title)).toBeVisible();
  }
  await drawer.getByRole('checkbox', { name: 'Собрать данные' }).click();
  await expect(drawer.getByText('1 из 2')).toBeVisible();

  await drawer.getByRole('button', { name: 'Перенести' }).click();
  const postpone = page.getByRole('dialog', { name: 'Перенести задачу' });
  await postpone.getByLabel('Причина').fill('Ждём данные от преподавателя');
  await postpone.getByRole('button', { name: 'Перенести' }).click();
  await expect(drawer.getByText('Перенесена').first()).toBeVisible();
  await expect(drawer.getByText('Причина: Ждём данные от преподавателя')).toBeVisible();

  await drawer.getByRole('checkbox', { name: 'Отметить выполненной' }).click();
  await expect(drawer.getByText('Выполнена').first()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(drawer).toBeHidden();

  await page.getByRole('link', { name: 'Завершённые' }).click();
  await expect(page.getByRole('button', { name: /Сдать лабораторную/ })).toBeVisible();
});

test('schedule: create, conflict with force, free time and dashboard', async ({ page }) => {
  await register(page);
  await page.goto('/schedule/day');

  const create = async (title: string, type: string, start: string, end: string) => {
    await page.getByRole('button', { name: 'Событие', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Новое событие' });
    await dialog.getByLabel('Название').fill(title);
    await dialog.getByRole('radio', { name: type }).click();
    await dialog.getByLabel('Начало').selectOption(start);
    await dialog.getByLabel('Конец').selectOption(end);
    return dialog;
  };

  let dialog = await create('Лекция', 'Фиксированное', '10:00', '11:30');
  await dialog.getByRole('button', { name: 'Сохранить' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole('button', { name: /Лекция/ })).toBeVisible();

  dialog = await create('Консультация', 'Фиксированное', '11:00', '12:00');
  await expect(dialog.getByText('Пересекается с:')).toBeVisible();
  await dialog.getByRole('button', { name: 'Сохранить' }).click();
  await expect(dialog.getByText('Конфликт с фиксированным событием:')).toBeVisible();
  await dialog.getByRole('button', { name: 'Сохранить всё равно' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole('button', { name: /Консультация/ })).toBeVisible();

  // Working window 07:00–23:00 minus 10:00–12:00 busy = 14 h free.
  await expect(page.getByText('14 ч 0 мин')).toBeVisible();

  await page.getByRole('link', { name: 'Главная' }).click();
  const widget = page.locator('section').filter({ hasText: 'Расписание на сегодня' }).last();
  await expect(widget.getByText('Лекция')).toBeVisible();
  await expect(widget.getByText('Консультация')).toBeVisible();
});

test('schedule: weekly series, edit one occurrence', async ({ page }) => {
  await register(page);
  await page.goto('/schedule/agenda');
  await page.getByRole('button', { name: 'Событие', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Новое событие' });
  await dialog.getByLabel('Название').fill('Йога');
  await dialog.getByLabel('Начало').selectOption('07:00');
  await dialog.getByLabel('Конец').selectOption('08:00');
  await dialog.getByLabel('Повтор').selectOption('daily');
  await dialog.getByRole('button', { name: 'Сохранить' }).click();
  await expect(dialog).toBeHidden();

  const items = page.getByRole('button', { name: /Йога/ });
  await expect(items).toHaveCount(14);

  await items.nth(1).click();
  const edit = page.getByRole('dialog', { name: 'Событие' });
  await edit.getByLabel('Название').fill('Йога на природе');
  await edit.getByRole('radio', { name: 'Только этому' }).check();
  await edit.getByRole('button', { name: 'Сохранить' }).click();
  await expect(edit).toBeHidden();
  await expect(page.getByRole('button', { name: /Йога на природе/ })).toHaveCount(1);
  await expect(page.getByRole('button', { name: /Йога/ })).toHaveCount(14);
});
