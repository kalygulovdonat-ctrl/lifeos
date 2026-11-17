import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Hourglass, Plus } from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router';

import { keys, scheduleApi } from '@/shared/api/planning';
import type { CalendarEvent } from '@/shared/api/types';
import { Alert, Button, PageHeader } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import {
  addDays,
  addMonths,
  clockOf,
  formatKey,
  formatTime,
  startOfMonth,
  startOfWeek,
} from '@/shared/utils/datetime';

import { EventEditor, type EditorTarget } from './EventEditor';
import { Agenda, MonthGrid } from './MonthGrid';
import styles from './schedule.module.css';
import { TimeGrid } from './TimeGrid';

const VIEWS = ['day', 'week', 'month', 'agenda'] as const;
type View = (typeof VIEWS)[number];
const AGENDA_DAYS = 14;

function rangeOf(
  view: View,
  date: string,
  weekStart: number,
): { from: string; to: string; days: string[] } {
  const span = (from: string, n: number) => {
    const days = Array.from({ length: n }, (_, i) => addDays(from, i));
    return { from, to: days[n - 1]!, days };
  };
  if (view === 'day') return span(date, 1);
  if (view === 'week') return span(startOfWeek(date, weekStart), 7);
  if (view === 'month') return span(startOfWeek(startOfMonth(date), weekStart), 42);
  return span(date, AGENDA_DAYS);
}

function shift(view: View, date: string, dir: 1 | -1): string {
  if (view === 'day') return addDays(date, dir);
  if (view === 'week') return addDays(date, 7 * dir);
  if (view === 'month') return addMonths(date, dir);
  return addDays(date, AGENDA_DAYS * dir);
}

export default function SchedulePage() {
  const { t } = useTranslation('schedule');
  const { view: rawView } = useParams();
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const prefs = usePrefs();
  const today = useToday();
  const errorMessage = useErrorMessage();
  const [editor, setEditor] = useState<EditorTarget | null>(null);

  const view = (rawView ?? 'week') as View;
  const date = search.get('date') ?? today;
  const range = rangeOf(view, date, prefs.weekStart);
  const events = useQuery({
    queryKey: keys.eventRange(range.from, range.to),
    queryFn: () => scheduleApi.range(range.from, range.to),
    placeholderData: (prev) => prev,
  });
  const free = useQuery({
    queryKey: keys.freeSlots(date),
    queryFn: () => scheduleApi.freeSlots(date),
    enabled: view === 'day',
  });

  if (!VIEWS.includes(view)) return <Navigate to="/schedule/week" replace />;

  const go = (next: string) => setSearch(next === today ? {} : { date: next });
  const list: CalendarEvent[] = events.data ?? [];

  const heading =
    view === 'day'
      ? formatKey(date, prefs.language, { weekday: 'long', day: 'numeric', month: 'long' })
      : view === 'month'
        ? formatKey(date, prefs.language, { month: 'long', year: 'numeric' })
        : `${formatKey(range.from, prefs.language, { day: 'numeric', month: 'short' })} – ${formatKey(range.to, prefs.language, { day: 'numeric', month: 'short', year: 'numeric' })}`;

  const create = (day: string, start: string) => setEditor({ mode: 'create', date: day, start });
  const nextSlot = () => {
    const now = clockOf(new Date(), prefs.timezone);
    const [h = 9] = now.split(':').map(Number);
    const start = date === today ? `${String(Math.min(h + 1, 23)).padStart(2, '0')}:00` : '09:00';
    create(
      view === 'week' || view === 'month'
        ? date >= range.from && date <= range.to
          ? date
          : range.from
        : date,
      start,
    );
  };

  return (
    <div className={styles.page}>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <Button icon={<Plus size={16} />} onClick={nextSlot}>
            {t('newEvent')}
          </Button>
        }
      />

      <div className={styles.toolbar}>
        <div className={styles.nav}>
          <button type="button" onClick={() => go(shift(view, date, -1))} aria-label={t('prev')}>
            <ChevronLeft size={18} />
          </button>
          <button type="button" className={styles.todayBtn} onClick={() => go(today)}>
            {t('today')}
          </button>
          <button type="button" onClick={() => go(shift(view, date, 1))} aria-label={t('next')}>
            <ChevronRight size={18} />
          </button>
          <h2 className={styles.heading}>
            {heading.charAt(0).toLocaleUpperCase() + heading.slice(1)}
          </h2>
        </div>
        <nav className={styles.views} aria-label={t('viewLabel')}>
          {VIEWS.map((v) => (
            <Link
              key={v}
              to={`/schedule/${v}${search.get('date') ? `?date=${date}` : ''}`}
              aria-current={v === view ? 'page' : undefined}
            >
              {v === view ? (
                <motion.span layoutId="schedule-view" className={styles.viewBg} />
              ) : null}
              {t(`views.${v}`)}
            </Link>
          ))}
        </nav>
      </div>

      {events.error ? <Alert>{errorMessage(events.error)}</Alert> : null}

      <div className={view === 'day' ? styles.dayLayout : undefined}>
        <div className={styles.surface} aria-busy={events.isFetching || undefined}>
          {view === 'day' || view === 'week' ? (
            <TimeGrid
              days={range.days}
              events={list}
              onCreate={create}
              onOpen={(event) => setEditor({ mode: 'edit', event })}
            />
          ) : view === 'month' ? (
            <MonthGrid
              first={range.from}
              month={date.slice(0, 7)}
              events={list}
              onDay={(day) => navigate(`/schedule/day?date=${day}`)}
              onOpen={(event) => setEditor({ mode: 'edit', event })}
            />
          ) : (
            <Agenda
              days={range.days}
              events={list}
              onOpen={(event) => setEditor({ mode: 'edit', event })}
            />
          )}
        </div>

        {view === 'day' && free.data ? (
          <aside className={styles.freePanel} aria-labelledby="free-title">
            <h3 id="free-title">
              <Hourglass size={16} /> {t('free.title')}
            </h3>
            <p className={styles.freeTotal}>
              <strong>
                {t('free.minutes', {
                  h: Math.floor(free.data.free_minutes / 60),
                  m: free.data.free_minutes % 60,
                })}
              </strong>
              <span>
                {t('free.busy', {
                  h: Math.floor(free.data.busy_minutes / 60),
                  m: free.data.busy_minutes % 60,
                })}
              </span>
            </p>
            {free.data.slots.length ? (
              <ul>
                {free.data.slots.map((s) => (
                  <li key={s.start_at}>
                    <button
                      type="button"
                      onClick={() => create(date, clockOf(new Date(s.start_at), prefs.timezone))}
                    >
                      <span>
                        {formatTime(new Date(s.start_at), prefs)} –{' '}
                        {formatTime(new Date(s.end_at), prefs)}
                      </span>
                      <small>{t('free.slotMinutes', { count: s.minutes })}</small>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.freeEmpty}>{t('free.none')}</p>
            )}
            <p className={styles.freeHint}>{t('free.hint')}</p>
          </aside>
        ) : null}
      </div>

      <EventEditor target={editor} onClose={() => setEditor(null)} />
    </div>
  );
}
