import { MapPin } from 'lucide-react';
import { motion } from 'motion/react';
import { useTranslation } from 'react-i18next';

import { Aurora } from '@/shared/components/brand';
import { CountUp, ProgressBar, ProgressRing, RevealText } from '@/shared/components/motion';
import { Badge } from '@/shared/components/ui';
import { useNow } from '@/shared/hooks/usePrefs';
import { useAuthStore } from '@/shared/store/authStore';
import {
  dayPart,
  dayWindow,
  formatClock,
  formatLongDate,
  formatTime,
  localHour,
  weekProgress,
  yearProgress,
} from '@/shared/utils/datetime';

import { DayWidgets } from './DayWidgets';
import styles from './dashboard.module.css';

const capitalize = (text: string) => text.charAt(0).toLocaleUpperCase() + text.slice(1);
const percent = (n: number) => `${Math.round(n)}%`;

/** DASH-001/002 plus live, honest time context: working day, week and year progress. */
export default function DashboardPage() {
  const { t } = useTranslation('dashboard');
  const profile = useAuthStore((s) => s.profile);
  const now = useNow();

  if (!profile) return null;
  const prefs = {
    language: profile.language,
    timezone: profile.timezone,
    timeFormat: profile.time_format,
  };
  const part = dayPart(localHour(now, profile.timezone));
  const start = profile.day_start_time.slice(0, 5);
  const end = profile.day_end_time.slice(0, 5);
  const day = dayWindow(now, profile.timezone, start, end);
  const week = weekProgress(now, profile.timezone, profile.week_start);
  const year = yearProgress(now, profile.timezone);

  const duration = (minutes: number) => {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return h > 0 ? t('units.hm', { h, m }) : t('units.m', { m });
  };
  const dayStatus =
    day.phase === 'during'
      ? t('day.left', { time: duration(day.minutesLeft) })
      : day.phase === 'before'
        ? t('day.before', { time: duration(day.minutesUntilStart) })
        : t('day.after');

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <Aurora />
        <div className={styles.heroText}>
          <motion.p
            className={styles.eyebrow}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <span>{capitalize(formatLongDate(now, prefs))}</span>
            <span className={styles.dot} aria-hidden="true" />
            <time dateTime={now.toISOString()}>{formatTime(now, prefs)}</time>
          </motion.p>
          <h1>
            <RevealText text={t(`greeting.${part}`, { name: profile.display_name })} delay={0.1} />
          </h1>
          <motion.p
            className={styles.lead}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.5 }}
          >
            {t(`lead.${part}`)}
          </motion.p>
          <motion.div
            className={styles.heroMeta}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.65 }}
          >
            <Badge icon={<MapPin size={12} />}>{t('timezoneNote', { tz: profile.timezone })}</Badge>
          </motion.div>
        </div>

        <motion.div
          className={styles.dayCard}
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.25, ease: [0.2, 0.7, 0.2, 1] }}
        >
          <ProgressRing value={day.progress}>
            <div className={styles.ringValue}>
              <strong>
                <CountUp value={day.progress * 100} format={percent} />
              </strong>
              <span>{t('day.title')}</span>
            </div>
          </ProgressRing>
          <div className={styles.dayMeta}>
            <span className={styles.dayStatus}>{dayStatus}</span>
            <span className={styles.dayWindow}>
              {formatClock(start, profile.time_format)} – {formatClock(end, profile.time_format)}
            </span>
          </div>
        </motion.div>

        <div className={styles.horizon}>
          <div>
            <div className={styles.horizonHead}>
              <span>{t('week.title')}</span>
              <CountUp value={week * 100} format={percent} />
            </div>
            <ProgressBar value={week} />
          </div>
          <div>
            <div className={styles.horizonHead}>
              <span>{t('year.title', { year: year.year })}</span>
              <CountUp value={year.progress * 100} format={percent} />
            </div>
            <ProgressBar value={year.progress} />
          </div>
        </div>
      </section>

      <DayWidgets />
    </div>
  );
}
