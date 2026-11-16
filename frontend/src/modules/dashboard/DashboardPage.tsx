import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Card } from '@/shared/components/ui';
import { useAuthStore } from '@/shared/store/authStore';
import { dayPart, formatLongDate, formatTime, localHour } from '@/shared/utils/datetime';

import styles from './dashboard.module.css';

const capitalize = (text: string) => text.charAt(0).toLocaleUpperCase() + text.slice(1);

/** DASH-001, DASH-002. Widgets (DASH-003…011) arrive in Phase 1. */
export default function DashboardPage() {
  const { t } = useTranslation('dashboard');
  const profile = useAuthStore((s) => s.profile);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  if (!profile) return null;
  const prefs = {
    language: profile.language,
    timezone: profile.timezone,
    timeFormat: profile.time_format,
  };
  const part = dayPart(localHour(now, profile.timezone));

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1>{t(`greeting.${part}`, { name: profile.display_name })}</h1>
        <p className={styles.date}>
          <span>{capitalize(formatLongDate(now, prefs))}</span>
          <span aria-hidden="true"> · </span>
          <time dateTime={now.toISOString()}>{formatTime(now, prefs)}</time>
        </p>
        <p className={styles.tz}>{t('timezoneNote', { tz: profile.timezone })}</p>
      </header>
      <Card>
        <p className={styles.note}>{t('foundationReady')}</p>
      </Card>
    </div>
  );
}
