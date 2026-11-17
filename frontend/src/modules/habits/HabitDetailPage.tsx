import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Archive,
  ArchiveRestore,
  ArrowLeft,
  Flame,
  Pause,
  Pencil,
  Trash2,
  Trophy,
} from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import styles from '@/modules/growth.module.css';
import { useInvalidatePlanning } from '@/modules/planning/hooks';
import { growthKeys, habitsApi } from '@/shared/api/growth';
import type { HabitDay } from '@/shared/api/types';
import { Modal } from '@/shared/components/overlay';
import { Alert, Button, PageHeader, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { addDays, formatKey, isoWeekday } from '@/shared/utils/datetime';

import { HabitEditor } from './HabitEditor';
import { useScheduleLabel } from './useScheduleLabel';

const HEATMAP_DAYS = 26 * 7;
const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`;

function cellState(d: HabitDay, today: string): string {
  if (d.paused) return 'paused';
  if (d.status) return d.status;
  if (!d.planned) return 'off';
  return d.date < today ? 'fail' : 'empty';
}

export default function HabitDetailPage() {
  const { habitId = '' } = useParams();
  const { t } = useTranslation('habits');
  const prefs = usePrefs();
  const today = useToday();
  const invalidate = useInvalidatePlanning();
  const errorMessage = useErrorMessage();
  const scheduleLabel = useScheduleLabel();
  const [editing, setEditing] = useState(false);
  const [pausing, setPausing] = useState(false);

  const habit = useQuery({
    queryKey: growthKeys.habit(habitId),
    queryFn: () => habitsApi.get(habitId),
  });
  const week = useQuery({
    queryKey: growthKeys.habitStats(habitId, 'week'),
    queryFn: () => habitsApi.stats(habitId, 'week'),
  });
  const month = useQuery({
    queryKey: growthKeys.habitStats(habitId, 'month'),
    queryFn: () => habitsApi.stats(habitId, 'month'),
  });
  // The heatmap starts on the first weekday so that rows are weekdays.
  const from = (() => {
    const raw = addDays(today, -HEATMAP_DAYS + 1);
    return addDays(raw, -((isoWeekday(raw) - prefs.weekStart + 7) % 7));
  })();
  const history = useQuery({
    queryKey: growthKeys.habitHistory(habitId, from, today),
    queryFn: () => habitsApi.history(habitId, from, today),
  });
  const archive = useMutation({
    mutationFn: () =>
      habit.data?.is_archived ? habitsApi.restore(habitId) : habitsApi.archive(habitId),
    onSettled: invalidate,
  });
  const voidLog = useMutation({ mutationFn: habitsApi.voidLog, onSettled: invalidate });
  const removePause = useMutation({ mutationFn: habitsApi.removePause, onSettled: invalidate });

  if (habit.error) return <Alert>{errorMessage(habit.error)}</Alert>;
  const h = habit.data;
  if (!h) return null;
  const unit = h.tracking_type === 'DURATION' ? t('min') : h.unit;
  const logs = (history.data?.logs ?? []).filter((l) => !l.is_voided).slice(0, 20);

  return (
    <div className={[styles.page, styles.narrow].join(' ')}>
      <Link to="/habits" className={styles.back}>
        <ArrowLeft size={15} /> {t('back')}
      </Link>
      <PageHeader
        title={h.name}
        description={`${t(`type.${h.tracking_type}`)} · ${scheduleLabel(h.schedule)}${h.is_archived ? ` · ${t('archived')}` : ''}`}
        actions={
          <div className={styles.row}>
            <Button
              variant="secondary"
              size="sm"
              icon={<Pencil size={15} />}
              onClick={() => setEditing(true)}
            >
              {t('edit')}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={<Pause size={15} />}
              onClick={() => setPausing(true)}
            >
              {t('pause.action')}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={h.is_archived ? <ArchiveRestore size={15} /> : <Archive size={15} />}
              onClick={() => archive.mutate()}
            >
              {h.is_archived ? t('restore') : t('archive')}
            </Button>
          </div>
        }
      />

      <dl className={styles.stats}>
        <div className={styles.stat}>
          <dt>
            <Flame size={13} /> {t('stats.current')}
          </dt>
          <dd>{week.data?.current_streak ?? '—'}</dd>
        </div>
        <div className={styles.stat}>
          <dt>
            <Trophy size={13} /> {t('stats.best')}
          </dt>
          <dd>{week.data?.best_streak ?? '—'}</dd>
        </div>
        <div className={styles.stat}>
          <dt>{t('stats.week')}</dt>
          <dd>
            {pct(week.data?.consistency)}
            {week.data?.eligible ? (
              <small>
                {' '}
                · {week.data.success}/{week.data.eligible}
              </small>
            ) : null}
          </dd>
        </div>
        <div className={styles.stat}>
          <dt>{t('stats.month')}</dt>
          <dd>
            {pct(month.data?.consistency)}
            {month.data?.eligible ? (
              <small>
                {' '}
                · {month.data.success}/{month.data.eligible}
              </small>
            ) : null}
          </dd>
        </div>
        {h.tracking_type === 'QUANTITY' || h.tracking_type === 'DURATION' ? (
          <div className={styles.stat}>
            <dt>{t('stats.total')}</dt>
            <dd>
              {Number(month.data?.total_value ?? 0)} <small>{unit}</small>
            </dd>
          </div>
        ) : null}
      </dl>
      <p className={styles.subtle}>{t('stats.hint')}</p>

      <section className={styles.panel} aria-labelledby="heatmap-title">
        <h2 id="heatmap-title">{t('heatmap.title')}</h2>
        <div className={styles.heatmap} role="img" aria-label={t('heatmap.title')}>
          {(history.data?.days ?? []).map((d) => (
            <i
              key={d.date}
              data-s={cellState(d, today)}
              title={`${formatKey(d.date, prefs.language, { day: 'numeric', month: 'short' })}: ${d.status ? t(`status.${d.status}`) : d.paused ? t('today.paused') : '—'}`}
            />
          ))}
        </div>
        <div className={styles.legend}>
          <span>
            <i style={{ background: 'var(--color-primary)' }} /> {t('status.DONE')}
          </span>
          <span>
            <i
              style={{
                background: 'color-mix(in srgb, var(--color-primary) 45%, var(--color-surface-2))',
              }}
            />{' '}
            {t('status.PARTIAL')}
          </span>
          <span>
            <i style={{ background: 'color-mix(in srgb, #14b8a6 40%, var(--color-surface-2))' }} />{' '}
            {t('heatmap.rest')}
          </span>
          <span>
            <i
              style={{
                background: 'color-mix(in srgb, var(--color-danger) 30%, var(--color-surface-2))',
              }}
            />{' '}
            {t('heatmap.missed')}
          </span>
        </div>
      </section>

      <div className={styles.split}>
        <section className={styles.panel} aria-labelledby="logs-title">
          <h2 id="logs-title">{t('logs.title')}</h2>
          {logs.length ? (
            <ul className={styles.list}>
              {logs.map((l) => (
                <li key={l.id} className={styles.item}>
                  <div className={styles.itemLink}>
                    <strong>
                      {formatKey(l.log_date, prefs.language, {
                        weekday: 'short',
                        day: 'numeric',
                        month: 'long',
                      })}
                    </strong>
                    <small>
                      {t(`status.${l.status}`)}
                      {l.value !== null
                        ? ` · ${Number(l.value)} ${l.unit_snapshot === 'min' ? t('min') : l.unit_snapshot}`
                        : ''}
                      {l.note ? ` · ${l.note}` : ''}
                    </small>
                  </div>
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={() => voidLog.mutate(l.id)}
                    aria-label={t('logs.void')}
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.empty}>{t('logs.empty')}</p>
          )}
          <p className={styles.subtle}>{t('logs.hint')}</p>
        </section>
        <aside className={styles.panel} aria-labelledby="pauses-title">
          <h2 id="pauses-title">{t('pause.title')}</h2>
          {h.pauses.length ? (
            <ul className={styles.list}>
              {h.pauses.map((p) => (
                <li key={p.id} className={styles.item}>
                  <div className={styles.itemLink}>
                    <strong>
                      {formatKey(p.start_date, prefs.language, { day: 'numeric', month: 'short' })}{' '}
                      –{' '}
                      {p.end_date
                        ? formatKey(p.end_date, prefs.language, { day: 'numeric', month: 'short' })
                        : t('pause.open')}
                    </strong>
                    {p.reason ? <small>{p.reason}</small> : null}
                  </div>
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={() => removePause.mutate(p.id)}
                    aria-label={t('pause.remove')}
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>{t('pause.none')}</p>
          )}
        </aside>
      </div>

      <HabitEditor open={editing} onClose={() => setEditing(false)} habit={h} />
      <PauseDialog habitId={h.id} open={pausing} onClose={() => setPausing(false)} />
    </div>
  );
}

function PauseDialog({
  habitId,
  open,
  onClose,
}: {
  habitId: string;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation('habits');
  const today = useToday();
  const errorMessage = useErrorMessage();
  const invalidate = useInvalidatePlanning();
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(addDays(today, 6));
  const [reason, setReason] = useState('');
  const save = useMutation({
    mutationFn: () =>
      habitsApi.pause(habitId, { start_date: start, end_date: end || null, reason }),
    onSuccess: onClose,
    onSettled: invalidate,
  });
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title={t('pause.title')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t('editor.cancel')}
          </Button>
          <Button loading={save.isPending} onClick={() => save.mutate()}>
            {t('pause.save')}
          </Button>
        </>
      }
    >
      <p className={styles.muted}>{t('pause.hint')}</p>
      <div className={styles.formGrid}>
        <TextField
          label={t('pause.start')}
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
        <TextField
          label={t('pause.end')}
          type="date"
          value={end}
          min={start}
          onChange={(e) => setEnd(e.target.value)}
        />
      </div>
      <TextField
        label={t('pause.reason')}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder={t('pause.reasonPlaceholder')}
        maxLength={200}
      />
      {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
    </Modal>
  );
}
