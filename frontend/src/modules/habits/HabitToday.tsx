import { useMutation } from '@tanstack/react-query';
import { Coffee, Flame, Plus, SkipForward, Undo2 } from 'lucide-react';
import { motion } from 'motion/react';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import styles from '@/modules/growth.module.css';
import { useInvalidatePlanning } from '@/modules/planning/hooks';
import { habitsApi } from '@/shared/api/growth';
import type { HabitLogStatus, TodayHabit } from '@/shared/api/types';
import { CheckButton } from '@/shared/components/overlay';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';

import h from './habits.module.css';
import { useScheduleLabel } from './useScheduleLabel';

const num = (v: string | null) => (v === null ? 0 : Number(v));
const fmt = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

export function HabitTodayRow({
  item,
  date,
  compact = false,
}: {
  item: TodayHabit;
  date: string;
  compact?: boolean;
}) {
  const { t } = useTranslation('habits');
  const invalidate = useInvalidatePlanning();
  const errorMessage = useErrorMessage();
  const scheduleLabel = useScheduleLabel();
  const habit = item.habit;
  const [value, setValue] = useState('');

  const log = useMutation({
    mutationFn: (input: { status?: HabitLogStatus; value?: string }) =>
      habitsApi.log(habit.id, { log_date: date, ...input }),
    // Clear only what was submitted: the user may already be typing the next value.
    onSuccess: (_data, vars) => setValue((current) => (current === vars.value ? '' : current)),
    onSettled: invalidate,
  });
  const undo = useMutation({
    mutationFn: () => Promise.all(item.log_ids.map((id) => habitsApi.voidLog(id))),
    onSettled: invalidate,
  });
  const busy = log.isPending || undo.isPending;
  const done = item.status === 'DONE';
  const skipped = item.status === 'SKIPPED' || item.status === 'REST' || item.status === 'MISSED';
  const target = num(item.target_value);
  const current = num(item.value);
  const unit = habit.tracking_type === 'DURATION' ? t('min') : habit.unit;
  const color = habit.color ?? '#8B5CF6';

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (Number(value) > 0) log.mutate({ value });
  };

  return (
    <motion.li
      layout
      className={h.today}
      data-done={done || undefined}
      data-muted={!item.planned || item.paused || undefined}
      style={{ ['--c' as string]: color }}
    >
      {habit.tracking_type === 'BOOLEAN' ? (
        <CheckButton
          size={30}
          checked={done || (log.isPending && log.variables?.status === undefined)}
          onChange={(next) => (next ? log.mutate({}) : undo.mutate())}
          label={done ? t('today.undo') : t('today.markDone', { name: habit.name })}
          disabled={busy || skipped}
        />
      ) : (
        <span
          className={h.ring}
          aria-hidden="true"
          style={{ ['--p' as string]: target ? Math.min(current / target, 1) : done ? 1 : 0 }}
        >
          <i />
        </span>
      )}
      <div className={h.todayMain}>
        <Link to={`/habits/${habit.id}`} className={h.todayName}>
          {habit.name}
        </Link>
        <span className={styles.subtle}>
          {scheduleLabel(habit.schedule)}
          {item.period_needed
            ? ` · ${t('today.period', { done: item.period_done, needed: item.period_needed })}`
            : ''}
          {habit.tracking_type !== 'BOOLEAN' && (target || current)
            ? ` · ${fmt(current)}${target ? ` / ${fmt(target)}` : ''} ${unit}`
            : ''}
          {item.paused
            ? ` · ${t('today.paused')}`
            : !item.planned
              ? ` · ${t('today.notPlanned')}`
              : ''}
        </span>
        {log.error ? <span className={h.error}>{errorMessage(log.error)}</span> : null}
      </div>
      {item.current_streak && !compact ? (
        <span className={h.streak} title={t('today.streak')}>
          <Flame size={14} /> {item.current_streak}
        </span>
      ) : null}

      {skipped ? (
        <>
          <span className={styles.chip} data-tone={item.status === 'REST' ? 'success' : 'warning'}>
            {t(`status.${item.status}`)}
          </span>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => undo.mutate()}
            aria-label={t('today.undo')}
          >
            <Undo2 size={15} />
          </button>
        </>
      ) : (
        <div className={h.actions}>
          {!compact &&
          (habit.tracking_type === 'QUANTITY' || habit.tracking_type === 'DURATION') ? (
            <form onSubmit={submit} className={h.addValue}>
              <input
                type="number"
                min={0}
                step="any"
                inputMode="decimal"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={unit || '+'}
                aria-label={t('today.addValue', { name: habit.name })}
              />
              <button
                type="submit"
                disabled={busy || !(Number(value) > 0)}
                aria-label={t('today.add')}
              >
                <Plus size={16} />
              </button>
            </form>
          ) : null}
          {!compact &&
          habit.tracking_type === 'SCALE' &&
          habit.scale_min !== null &&
          habit.scale_max !== null ? (
            item.status ? (
              <>
                <span className={styles.chip} data-tone={done ? 'success' : 'warning'}>
                  {fmt(current)} / {habit.scale_max}
                </span>
                <button
                  type="button"
                  className={styles.iconBtn}
                  onClick={() => undo.mutate()}
                  aria-label={t('today.undo')}
                >
                  <Undo2 size={15} />
                </button>
              </>
            ) : (
              <div className={h.scale} role="group" aria-label={habit.name}>
                {Array.from(
                  { length: Math.min(habit.scale_max - habit.scale_min + 1, 10) },
                  (_, i) => habit.scale_min! + i,
                ).map((n) => (
                  <button
                    key={n}
                    type="button"
                    disabled={busy}
                    onClick={() => log.mutate({ value: String(n) })}
                  >
                    {n}
                  </button>
                ))}
              </div>
            )
          ) : null}
          {!item.status && !compact ? (
            <>
              <button
                type="button"
                className={styles.iconBtn}
                disabled={busy}
                onClick={() => log.mutate({ status: 'REST' })}
                title={t('status.REST')}
                aria-label={t('status.REST')}
              >
                <Coffee size={15} />
              </button>
              <button
                type="button"
                className={styles.iconBtn}
                disabled={busy}
                onClick={() => log.mutate({ status: 'SKIPPED' })}
                title={t('status.SKIPPED')}
                aria-label={t('status.SKIPPED')}
              >
                <SkipForward size={15} />
              </button>
            </>
          ) : null}
          {!compact &&
          habit.tracking_type !== 'BOOLEAN' &&
          habit.tracking_type !== 'SCALE' &&
          item.log_ids.length ? (
            <button
              type="button"
              className={styles.iconBtn}
              onClick={() => undo.mutate()}
              aria-label={t('today.undo')}
            >
              <Undo2 size={15} />
            </button>
          ) : null}
        </div>
      )}
    </motion.li>
  );
}
