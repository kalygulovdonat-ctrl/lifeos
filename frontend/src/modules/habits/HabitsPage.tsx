import { useMutation, useQuery } from '@tanstack/react-query';
import { ArchiveRestore, ChevronLeft, ChevronRight, Plus, Repeat } from 'lucide-react';
import { AnimatePresence } from 'motion/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import styles from '@/modules/growth.module.css';
import { useInvalidatePlanning } from '@/modules/planning/hooks';
import { growthKeys, habitsApi } from '@/shared/api/growth';
import { Button, EmptyState, PageHeader } from '@/shared/components/ui';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { addDays, formatKey } from '@/shared/utils/datetime';

import { HabitEditor } from './HabitEditor';
import { HabitTodayRow } from './HabitToday';
import { useScheduleLabel } from './useScheduleLabel';
import h from './habits.module.css';

export default function HabitsPage() {
  const { t } = useTranslation('habits');
  const prefs = usePrefs();
  const today = useToday();
  const [date, setDate] = useState(today);
  const [creating, setCreating] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const scheduleLabel = useScheduleLabel();
  const invalidate = useInvalidatePlanning();

  const day = useQuery({
    queryKey: growthKeys.habitToday(date),
    queryFn: () => habitsApi.today(date),
  });
  const archived = useQuery({
    queryKey: growthKeys.habitList(true),
    queryFn: () => habitsApi.list(true),
    enabled: showArchived,
  });
  const restore = useMutation({ mutationFn: habitsApi.restore, onSettled: invalidate });

  const items = day.data?.results ?? [];
  const planned = items.filter((i) => i.planned && !i.paused);
  const other = items.filter((i) => !i.planned || i.paused);
  const done = planned.filter((i) => i.status === 'DONE').length;
  const label =
    date === today
      ? t('today.title')
      : formatKey(date, prefs.language, { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className={[styles.page, styles.narrow].join(' ')}>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <Button icon={<Plus size={16} />} onClick={() => setCreating(true)}>
            {t('new')}
          </Button>
        }
      />

      <section className={styles.panel} aria-labelledby="habits-day">
        <div className={styles.panelHead}>
          <div className={styles.row}>
            <button
              type="button"
              className={styles.iconBtn}
              onClick={() => setDate(addDays(date, -1))}
              aria-label={t('prevDay')}
            >
              <ChevronLeft size={18} />
            </button>
            <h2 id="habits-day">{label.charAt(0).toLocaleUpperCase() + label.slice(1)}</h2>
            <button
              type="button"
              className={styles.iconBtn}
              onClick={() => setDate(addDays(date, 1))}
              disabled={date >= today}
              aria-label={t('nextDay')}
            >
              <ChevronRight size={18} />
            </button>
          </div>
          {planned.length ? (
            <div className={h.summary}>
              <strong>
                {done}/{planned.length}
              </strong>
              <div className={styles.bar} style={{ width: 140 }} aria-hidden="true">
                <i style={{ width: `${planned.length ? (done / planned.length) * 100 : 0}%` }} />
              </div>
            </div>
          ) : null}
        </div>

        {day.isLoading ? null : items.length === 0 ? (
          <EmptyState
            icon={<Repeat size={28} />}
            title={t('empty.title')}
            description={t('empty.description')}
            action={
              <Button icon={<Plus size={16} />} onClick={() => setCreating(true)}>
                {t('new')}
              </Button>
            }
          />
        ) : (
          <>
            <ul className={styles.list}>
              <AnimatePresence initial={false}>
                {planned.map((item) => (
                  <HabitTodayRow key={item.habit.id} item={item} date={date} />
                ))}
              </AnimatePresence>
            </ul>
            {other.length ? (
              <>
                <p className={styles.subtle}>{t('today.otherTitle')}</p>
                <ul className={styles.list}>
                  {other.map((item) => (
                    <HabitTodayRow key={item.habit.id} item={item} date={date} />
                  ))}
                </ul>
              </>
            ) : null}
          </>
        )}
      </section>

      <div>
        <button
          type="button"
          className={styles.back}
          onClick={() => setShowArchived((v) => !v)}
          style={{
            border: 0,
            background: 'none',
            color: 'var(--color-primary)',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          {showArchived ? t('hideArchived') : t('showArchived')}
        </button>
      </div>
      {showArchived ? (
        archived.data?.length ? (
          <ul className={styles.list}>
            {archived.data.map((habit) => (
              <li key={habit.id} className={styles.item}>
                <Link to={`/habits/${habit.id}`} className={styles.itemLink}>
                  <strong>{habit.name}</strong>
                  <small>{scheduleLabel(habit.schedule)}</small>
                </Link>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<ArchiveRestore size={15} />}
                  onClick={() => restore.mutate(habit.id)}
                >
                  {t('restore')}
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.muted}>{t('noArchived')}</p>
        )
      ) : null}

      <HabitEditor open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
