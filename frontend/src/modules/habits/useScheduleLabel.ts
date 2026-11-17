import { useTranslation } from 'react-i18next';

import type { HabitSchedule } from '@/shared/api/types';

/** "Каждый день", "Пн, Ср, Пт", "3 раза в неделю". */
export function useScheduleLabel() {
  const { t } = useTranslation('habits');
  return (s: HabitSchedule | null) => {
    if (!s) return '';
    switch (s.frequency_type) {
      case 'WEEKDAYS':
        return (['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'] as const)
          .filter((_, i) => (s.weekdays_mask ?? 0) & (1 << i))
          .map((d) => t(`weekday.${d}`))
          .join(', ');
      case 'TIMES_PER_WEEK':
        return t('freqLabel.TIMES_PER_WEEK', { count: s.times_per_period ?? 1 });
      case 'TIMES_PER_MONTH':
        return t('freqLabel.TIMES_PER_MONTH', { count: s.times_per_period ?? 1 });
      case 'EVERY_N_DAYS':
        return t('freqLabel.EVERY_N_DAYS', { count: s.interval_days ?? 2 });
      default:
        return t('freq.DAILY');
    }
  };
}
