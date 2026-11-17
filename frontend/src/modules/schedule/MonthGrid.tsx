import { useTranslation } from 'react-i18next';

import { TIME_TYPE_META } from '@/modules/planning/meta';
import type { CalendarEvent } from '@/shared/api/types';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { addDays, formatKey, formatTime } from '@/shared/utils/datetime';

import { eventKey, eventsOnDay } from './layout';
import styles from './schedule.module.css';

const MAX_CHIPS = 3;

export function MonthGrid({
  first,
  month,
  events,
  onDay,
  onOpen,
}: {
  first: string;
  month: string;
  events: CalendarEvent[];
  onDay: (day: string) => void;
  onOpen: (event: CalendarEvent) => void;
}) {
  const { t } = useTranslation('schedule');
  const prefs = usePrefs();
  const today = useToday();
  const days = Array.from({ length: 42 }, (_, i) => addDays(first, i));

  return (
    <div className={styles.month}>
      {days.slice(0, 7).map((d) => (
        <span key={`h-${d}`} className={styles.monthHead}>
          {formatKey(d, prefs.language, { weekday: 'short' })}
        </span>
      ))}
      {days.map((day) => {
        const items = eventsOnDay(events, day, prefs.timezone).filter(
          (e) => e.status !== 'CANCELLED',
        );
        return (
          <div
            key={day}
            className={styles.monthCell}
            data-outside={!day.startsWith(month) || undefined}
            data-today={day === today || undefined}
          >
            <button type="button" className={styles.monthDay} onClick={() => onDay(day)}>
              {Number(day.slice(8))}
            </button>
            {items.slice(0, MAX_CHIPS).map((e) => (
              <button
                type="button"
                key={eventKey(e)}
                className={styles.chip}
                style={{ ['--c' as string]: e.color ?? TIME_TYPE_META[e.time_type].color }}
                onClick={() => onOpen(e)}
              >
                <i />
                <span>
                  {formatTime(new Date(e.start_at), prefs)} {e.title}
                </span>
              </button>
            ))}
            {items.length > MAX_CHIPS ? (
              <button type="button" className={styles.more} onClick={() => onDay(day)}>
                {t('more', { count: items.length - MAX_CHIPS })}
              </button>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function Agenda({
  days,
  events,
  onOpen,
}: {
  days: string[];
  events: CalendarEvent[];
  onOpen: (event: CalendarEvent) => void;
}) {
  const { t } = useTranslation('schedule');
  const prefs = usePrefs();
  const today = useToday();
  const withEvents = days
    .map((day) => ({ day, items: eventsOnDay(events, day, prefs.timezone) }))
    .filter((d) => d.items.length);

  if (!withEvents.length) return <p className={styles.agendaEmpty}>{t('agendaEmpty')}</p>;

  return (
    <div className={styles.agenda}>
      {withEvents.map(({ day, items }) => (
        <section key={day} aria-label={day}>
          <h3 data-today={day === today || undefined}>
            <b>{Number(day.slice(8))}</b>
            <span>{formatKey(day, prefs.language, { weekday: 'long', month: 'long' })}</span>
          </h3>
          <ul>
            {items.map((e) => {
              const meta = TIME_TYPE_META[e.time_type];
              const Icon = meta.icon;
              return (
                <li key={eventKey(e)}>
                  <button
                    type="button"
                    onClick={() => onOpen(e)}
                    style={{ ['--c' as string]: e.color ?? meta.color }}
                    data-status={e.status}
                  >
                    <time>
                      {formatTime(new Date(e.start_at), prefs)}
                      <small>{formatTime(new Date(e.end_at), prefs)}</small>
                    </time>
                    <i aria-hidden="true">
                      <Icon size={15} />
                    </i>
                    <span>
                      <strong>{e.title}</strong>
                      <small>
                        {t(`timeType.${e.time_type}`)}
                        {e.location ? ` · ${e.location}` : ''}
                        {e.task ? ` · ${e.task.title ?? ''}` : ''}
                      </small>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
