import { Repeat } from 'lucide-react';
import { motion } from 'motion/react';
import { useEffect, useMemo, useRef, type MouseEvent } from 'react';

import { TIME_TYPE_META } from '@/modules/planning/meta';
import type { CalendarEvent } from '@/shared/api/types';
import { useNow, usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { formatClock, formatKey, formatTime, minutesOfDay } from '@/shared/utils/datetime';

import { eventKey, layoutDay } from './layout';
import styles from './schedule.module.css';

export const HOUR_PX = 52;
const toMinutes = (hhmm: string) => {
  const [h = 0, m = 0] = hhmm.split(':').map(Number);
  return h * 60 + m;
};

export function TimeGrid({
  days,
  events,
  onCreate,
  onOpen,
}: {
  days: string[];
  events: CalendarEvent[];
  onCreate: (day: string, hhmm: string) => void;
  onOpen: (event: CalendarEvent) => void;
}) {
  const prefs = usePrefs();
  const today = useToday();
  const now = useNow(60_000);
  const scroller = useRef<HTMLDivElement>(null);
  const workStart = toMinutes(prefs.dayStart);
  const workEnd = toMinutes(prefs.dayEnd);

  useEffect(() => {
    scroller.current?.scrollTo({ top: Math.max(0, (workStart / 60 - 1) * HOUR_PX) });
  }, [workStart]);

  const placed = useMemo(
    () => days.map((day) => layoutDay(events, day, prefs.timezone)),
    [days, events, prefs.timezone],
  );

  const handleClick = (day: string) => (e: MouseEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const minute = Math.floor(((e.clientY - rect.top) / HOUR_PX) * 2) * 30;
    const clamped = Math.min(Math.max(minute, 0), 23 * 60);
    const hhmm = `${String(Math.floor(clamped / 60)).padStart(2, '0')}:${clamped % 60 ? '30' : '00'}`;
    onCreate(day, hhmm);
  };

  const nowMinute = minutesOfDay(now, prefs.timezone);

  return (
    <div className={styles.grid} style={{ ['--days' as string]: days.length }}>
      <div className={styles.gridHead}>
        <span />
        {days.map((day) => (
          <div key={day} className={styles.dayHead} data-today={day === today || undefined}>
            <span>{formatKey(day, prefs.language, { weekday: 'short' })}</span>
            <b>{Number(day.slice(8))}</b>
          </div>
        ))}
      </div>
      <div className={styles.gridScroll} ref={scroller}>
        <div className={styles.gridBody} style={{ height: 24 * HOUR_PX }}>
          <div className={styles.hours} aria-hidden="true">
            {Array.from({ length: 24 }, (_, h) => (
              <span key={h} style={{ top: h * HOUR_PX }}>
                {h ? formatClock(`${String(h).padStart(2, '0')}:00`, prefs.timeFormat) : ''}
              </span>
            ))}
          </div>
          {days.map((day, i) => (
            <div
              key={day}
              className={styles.dayCol}
              onClick={handleClick(day)}
              data-today={day === today || undefined}
            >
              <span
                className={styles.offHours}
                style={{ top: 0, height: (workStart / 60) * HOUR_PX }}
                aria-hidden="true"
              />
              <span
                className={styles.offHours}
                style={{ top: (workEnd / 60) * HOUR_PX, bottom: 0 }}
                aria-hidden="true"
              />
              {placed[i]!.map((p, index) => {
                const meta = TIME_TYPE_META[p.event.time_type];
                const color = p.event.color ?? meta.color;
                const height = ((p.bottom - p.top) / 60) * HOUR_PX;
                return (
                  <motion.button
                    type="button"
                    key={eventKey(p.event)}
                    className={styles.block}
                    data-type={p.event.time_type}
                    data-status={p.event.status}
                    data-short={height < 40 || undefined}
                    style={{
                      top: (p.top / 60) * HOUR_PX + 1,
                      height: height - 2,
                      left: `calc(${(p.column / p.columns) * 100}% + 2px)`,
                      width: `calc(${100 / p.columns}% - 4px)`,
                      ['--c' as string]: color,
                    }}
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: Math.min(index * 0.03, 0.3), duration: 0.25 }}
                    onClick={() => onOpen(p.event)}
                  >
                    <strong>
                      {p.event.recurrence ? <Repeat size={11} aria-hidden="true" /> : null}
                      {p.event.title}
                    </strong>
                    <span>
                      {formatTime(new Date(p.event.start_at), prefs)} –{' '}
                      {formatTime(new Date(p.event.end_at), prefs)}
                    </span>
                  </motion.button>
                );
              })}
              {day === today ? (
                <span
                  className={styles.nowLine}
                  style={{ top: (nowMinute / 60) * HOUR_PX }}
                  aria-hidden="true"
                />
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
