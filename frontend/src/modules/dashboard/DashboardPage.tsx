import {
  ArrowUpRight,
  CalendarDays,
  Clock,
  Flame,
  Hourglass,
  ListTodo,
  MapPin,
  Target,
  type LucideIcon,
} from 'lucide-react';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { Aurora } from '@/shared/components/brand';
import { CountUp, ProgressBar, ProgressRing, RevealText } from '@/shared/components/motion';
import { riseChild, spotlight, staggerParent } from '@/shared/components/motion-utils';
import { Badge, IconTile } from '@/shared/components/ui';
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

import styles from './dashboard.module.css';

const capitalize = (text: string) => text.charAt(0).toLocaleUpperCase() + text.slice(1);
const percent = (n: number) => `${Math.round(n)}%`;

/** Widgets of DASH-003…009. Real data arrives with their modules; until then, an honest empty state. */
const WIDGETS: ReadonlyArray<{
  key: 'schedule' | 'tasks' | 'habits' | 'goals' | 'free' | 'focus';
  icon: LucideIcon;
  to: string;
  phase: string;
}> = [
  { key: 'schedule', icon: CalendarDays, to: '/schedule', phase: 'Phase 1' },
  { key: 'tasks', icon: ListTodo, to: '/tasks', phase: 'Phase 1' },
  { key: 'free', icon: Hourglass, to: '/schedule', phase: 'Phase 1' },
  { key: 'habits', icon: Flame, to: '/habits', phase: 'Phase 2' },
  { key: 'goals', icon: Target, to: '/goals', phase: 'Phase 2' },
  { key: 'focus', icon: Clock, to: '/time', phase: 'Phase 2' },
];

function useNow(intervalMs = 30_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

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

      <section aria-labelledby="today-title" className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 id="today-title">{t('todayTitle')}</h2>
          <p>{t('foundationReady')}</p>
        </div>
        <motion.div
          className={styles.grid}
          variants={staggerParent}
          initial="hidden"
          animate="show"
        >
          {WIDGETS.map(({ key, icon: Icon, to, phase }, index) => (
            <motion.div
              key={key}
              variants={riseChild}
              className={index === 0 ? styles.wide : undefined}
            >
              <Link to={to} viewTransition className={styles.widget} onPointerMove={spotlight}>
                <span className={styles.widgetGlow} aria-hidden="true" />
                <div className={styles.widgetHead}>
                  <IconTile size={40}>
                    <Icon size={19} />
                  </IconTile>
                  <Badge tone="accent">{phase}</Badge>
                </div>
                <h3>{t(`widgets.${key}.title`)}</h3>
                {index === 0 ? <TimelinePreview /> : null}
                <p>{t(`widgets.${key}.empty`)}</p>
                <span className={styles.widgetLink}>
                  {t('openModule')}
                  <ArrowUpRight size={15} aria-hidden="true" />
                </span>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      </section>
    </div>
  );
}

/** Empty day grid hinting at the future schedule view (no fake events). */
function TimelinePreview() {
  const hours = [8, 10, 12, 14, 16, 18, 20];
  return (
    <div className={styles.timeline} aria-hidden="true">
      {hours.map((h) => (
        <div key={h} className={styles.slot}>
          <span>{String(h).padStart(2, '0')}:00</span>
          <i />
        </div>
      ))}
    </div>
  );
}
