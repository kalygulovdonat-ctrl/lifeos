import { useTranslation } from 'react-i18next';

import type { Task } from '@/shared/api/types';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { addDays, formatKey, formatTime } from '@/shared/utils/datetime';

/** "Сегодня / Завтра / 18 нояб." plus time when the deadline has one. */
export function useDueLabel() {
  const { t } = useTranslation('tasks');
  const prefs = usePrefs();
  const today = useToday();
  return (task: Pick<Task, 'due_date' | 'due_at' | 'due_has_time'>) => {
    if (!task.due_date) return null;
    const day =
      task.due_date === today
        ? t('due.today')
        : task.due_date === addDays(today, 1)
          ? t('due.tomorrow')
          : task.due_date === addDays(today, -1)
            ? t('due.yesterday')
            : formatKey(task.due_date, prefs.language, { day: 'numeric', month: 'short' });
    return task.due_has_time && task.due_at
      ? `${day}, ${formatTime(new Date(task.due_at), prefs)}`
      : day;
  };
}
