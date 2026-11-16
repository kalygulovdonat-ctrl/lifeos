import {
  ArrowRight,
  CalendarDays,
  Clock,
  Flame,
  Hourglass,
  ListTodo,
  MapPin,
  Target,
  type LucideIcon,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { Badge, Card, IconTile } from '@/shared/components/ui';
import { useAuthStore } from '@/shared/store/authStore';
import { dayPart, formatLongDate, formatTime, localHour } from '@/shared/utils/datetime';

import styles from './dashboard.module.css';

const capitalize = (text: string) => text.charAt(0).toLocaleUpperCase() + text.slice(1);

/** Widgets of DASH-003…009. They show real data once their modules ship; until then, an honest empty state. */
const WIDGETS: ReadonlyArray<{
  key: 'schedule' | 'tasks' | 'habits' | 'goals' | 'free' | 'focus';
  icon: LucideIcon;
  to: string;
  phase: string;
  wide?: boolean;
}> = [
  { key: 'schedule', icon: CalendarDays, to: '/schedule', phase: 'Phase 1', wide: true },
  { key: 'tasks', icon: ListTodo, to: '/tasks', phase: 'Phase 1' },
  { key: 'free', icon: Hourglass, to: '/schedule', phase: 'Phase 1' },
  { key: 'habits', icon: Flame, to: '/habits', phase: 'Phase 2' },
  { key: 'goals', icon: Target, to: '/goals', phase: 'Phase 2' },
  { key: 'focus', icon: Clock, to: '/time', phase: 'Phase 2' },
];

/** DASH-001, DASH-002 + previews of the widgets delivered by later phases. */
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
      <section className={styles.hero}>
        <div className={styles.heroText}>
          <p className={styles.eyebrow}>
            <span>{capitalize(formatLongDate(now, prefs))}</span>
            <span className={styles.dot} aria-hidden="true" />
            <time dateTime={now.toISOString()}>{formatTime(now, prefs)}</time>
          </p>
          <h1>{t(`greeting.${part}`, { name: profile.display_name })}</h1>
          <p className={styles.lead}>{t(`lead.${part}`)}</p>
        </div>
        <div className={styles.heroMeta}>
          <Badge icon={<MapPin size={12} />}>{t('timezoneNote', { tz: profile.timezone })}</Badge>
        </div>
      </section>

      <section aria-labelledby="today-title" className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 id="today-title">{t('todayTitle')}</h2>
          <p>{t('foundationReady')}</p>
        </div>
        <div className={styles.grid}>
          {WIDGETS.map(({ key, icon: Icon, to, phase, wide }) => (
            <Card key={key} as="article" className={wide ? styles.wide : undefined}>
              <div className={styles.widgetHead}>
                <IconTile size={38}>
                  <Icon size={19} />
                </IconTile>
                <div className={styles.widgetTitle}>
                  <h3>{t(`widgets.${key}.title`)}</h3>
                  <Badge tone="accent">{phase}</Badge>
                </div>
              </div>
              {wide ? <TimelinePreview /> : null}
              <p className={styles.widgetText}>{t(`widgets.${key}.empty`)}</p>
              <Link to={to} className={styles.widgetLink}>
                {t('openModule')}
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </Card>
          ))}
        </div>
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
