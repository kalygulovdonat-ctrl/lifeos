import { useMutation, useQuery } from '@tanstack/react-query';
import { Brain, Pause, Play, Plus, Square, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useCategories, useInvalidatePlanning } from '@/modules/planning/hooks';
import styles from '@/modules/growth.module.css';
import { ApiError } from '@/shared/api/client';
import { growthKeys, timeApi } from '@/shared/api/growth';
import { keys, tasksApi } from '@/shared/api/planning';
import { Aurora } from '@/shared/components/brand';
import { Modal, Notice } from '@/shared/components/overlay';
import { Alert, Button, PageHeader, SelectField, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import {
  addDays,
  clockOf,
  clockOptions,
  formatKey,
  formatTime,
  startOfWeek,
  zonedIso,
} from '@/shared/utils/datetime';

import { formatStopwatch, useMinutesLabel, useTimer } from './useTimer';

function useOpenTasks() {
  const q = { status: 'OPEN', ordering: 'due_at' };
  return (
    useQuery({ queryKey: keys.taskList(q), queryFn: () => tasksApi.list(q) }).data?.results ?? []
  );
}

export default function TimePage() {
  const { t } = useTranslation('time');
  const prefs = usePrefs();
  const today = useToday();
  const errorMessage = useErrorMessage();
  const invalidate = useInvalidatePlanning();
  const timer = useTimer();
  const fmtMinutes = useMinutesLabel();
  const tasks = useOpenTasks();
  const [description, setDescription] = useState('');
  const [taskId, setTaskId] = useState('');
  const [focus, setFocus] = useState(true);
  const [range, setRange] = useState<'day' | 'week'>('day');
  const [manualOpen, setManualOpen] = useState(false);

  const from = range === 'day' ? today : startOfWeek(today, prefs.weekStart);
  const to = range === 'day' ? today : addDays(from, 6);
  const entries = useQuery({
    queryKey: growthKeys.timeEntries(from, to),
    queryFn: () => timeApi.entries(from, to),
  });
  const weekFrom = startOfWeek(today, prefs.weekStart);
  const pva = useQuery({
    queryKey: growthKeys.planVsActual(weekFrom, addDays(weekFrom, 6)),
    queryFn: () => timeApi.planVsActual(weekFrom, addDays(weekFrom, 6)),
  });
  const remove = useMutation({ mutationFn: timeApi.remove, onSettled: invalidate });

  const entry = timer.entry;
  const running = entry?.status === 'RUNNING';
  const paused = entry?.status === 'PAUSED';

  return (
    <div className={styles.page}>
      <PageHeader title={t('title')} description={t('subtitle')} />

      <section className={styles.timer} aria-label={t('timer.label')}>
        <Aurora />
        <p className={styles.timerMeta}>
          {entry
            ? `${entry.task?.title ?? (entry.description || t('timer.untitled'))}${entry.is_focus ? ` · ${t('timer.focus')}` : ''}`
            : t('timer.idle')}
        </p>
        <p className={styles.clock} data-paused={paused || undefined} role="timer" aria-live="off">
          {formatStopwatch(timer.seconds)}
        </p>
        {!entry ? (
          <div className={styles.timerInputs}>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('timer.description')}
              aria-label={t('timer.description')}
              maxLength={300}
            />
            <select
              value={taskId}
              onChange={(e) => setTaskId(e.target.value)}
              aria-label={t('timer.task')}
            >
              <option value="">{t('timer.noTask')}</option>
              {tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
            <label className={styles.toggle}>
              <input type="checkbox" checked={focus} onChange={(e) => setFocus(e.target.checked)} />
              <Brain size={15} /> {t('timer.focus')}
            </label>
          </div>
        ) : null}
        <div className={styles.timerActions}>
          {!entry ? (
            <button
              type="button"
              className={styles.timerBtn}
              data-primary
              disabled={timer.busy}
              onClick={() =>
                timer.start.mutate(
                  { description: description.trim(), task_id: taskId || null, is_focus: focus },
                  { onSuccess: () => setDescription('') },
                )
              }
            >
              <Play size={17} /> {t('timer.start')}
            </button>
          ) : (
            <>
              {running ? (
                <button
                  type="button"
                  className={styles.timerBtn}
                  disabled={timer.busy}
                  onClick={() => timer.pause.mutate()}
                >
                  <Pause size={17} /> {t('timer.pause')}
                </button>
              ) : (
                <button
                  type="button"
                  className={styles.timerBtn}
                  disabled={timer.busy}
                  onClick={() => timer.resume.mutate()}
                >
                  <Play size={17} /> {t('timer.resume')}
                </button>
              )}
              <button
                type="button"
                className={styles.timerBtn}
                data-primary
                disabled={timer.busy}
                onClick={() => timer.stop.mutate()}
              >
                <Square size={15} /> {t('timer.stop')}
              </button>
              <button
                type="button"
                className={styles.timerBtn}
                disabled={timer.busy}
                onClick={() => timer.discard.mutate()}
              >
                <X size={16} /> {t('timer.discard')}
              </button>
            </>
          )}
        </div>
        {timer.error ? <Alert>{errorMessage(timer.error)}</Alert> : null}
      </section>

      <div className={styles.split}>
        <section className={styles.panel} aria-labelledby="entries-title">
          <div className={styles.panelHead}>
            <h2 id="entries-title">
              {t('entries.title')}
              {entries.data ? (
                <span className={styles.chip} data-tone="accent">
                  {fmtMinutes(Math.round(entries.data.total_seconds / 60))}
                </span>
              ) : null}
            </h2>
            <div className={styles.row}>
              <div className={styles.pills}>
                {(['day', 'week'] as const).map((r) => (
                  <button
                    type="button"
                    key={r}
                    aria-pressed={range === r}
                    onClick={() => setRange(r)}
                  >
                    {t(`entries.${r}`)}
                  </button>
                ))}
              </div>
              <Button
                size="sm"
                variant="secondary"
                icon={<Plus size={15} />}
                onClick={() => setManualOpen(true)}
              >
                {t('entries.add')}
              </Button>
            </div>
          </div>
          {entries.data?.results.length ? (
            <ul className={styles.list}>
              {entries.data.results.map((e) => (
                <li key={e.id} className={styles.item}>
                  <div className={styles.itemLink}>
                    <strong>{e.task?.title ?? (e.description || t('timer.untitled'))}</strong>
                    <small>
                      {range === 'week'
                        ? `${formatKey(clockDate(e.started_at, prefs.timezone), prefs.language, { weekday: 'short', day: 'numeric' })}, `
                        : ''}
                      {formatTime(new Date(e.started_at), prefs)} –{' '}
                      {formatTime(new Date(e.ended_at!), prefs)}
                      {e.is_focus ? ` · ${t('timer.focus')}` : ''}
                      {e.source === 'MANUAL' ? ` · ${t('entries.manual')}` : ''}
                    </small>
                  </div>
                  <span className={styles.chip}>
                    {fmtMinutes(Math.round((e.duration_seconds ?? 0) / 60))}
                  </span>
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={() => remove.mutate(e.id)}
                    aria-label={t('entries.delete')}
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.empty}>{t('entries.empty')}</p>
          )}
        </section>

        <aside className={styles.panel} aria-labelledby="pva-title">
          <h2 id="pva-title">{t('pva.title')}</h2>
          {pva.data ? (
            <>
              <p className={styles.muted}>
                {pva.data.accuracy === null
                  ? t('pva.noPlan')
                  : t('pva.accuracy', { value: Math.round(pva.data.accuracy * 100) })}
              </p>
              {pva.data.accuracy !== null ? (
                <div className={styles.bar} aria-hidden="true">
                  <i style={{ width: `${Math.round(pva.data.accuracy * 100)}%` }} />
                </div>
              ) : null}
              <dl className={styles.stats}>
                <div className={styles.stat}>
                  <dt>{t('pva.planned')}</dt>
                  <dd>{fmtMinutes(pva.data.planned_minutes)}</dd>
                </div>
                <div className={styles.stat}>
                  <dt>{t('pva.actual')}</dt>
                  <dd>{fmtMinutes(pva.data.actual_minutes)}</dd>
                </div>
                <div className={styles.stat}>
                  <dt>{t('pva.focus')}</dt>
                  <dd>{fmtMinutes(pva.data.focus_minutes)}</dd>
                </div>
                <div className={styles.stat}>
                  <dt>{t('pva.unplanned')}</dt>
                  <dd>{fmtMinutes(pva.data.unplanned_minutes)}</dd>
                </div>
              </dl>
              <p className={styles.subtle}>{t('pva.hint')}</p>
            </>
          ) : null}
        </aside>
      </div>

      <ManualEntry open={manualOpen} onClose={() => setManualOpen(false)} tasks={tasks} />
    </div>
  );
}

function clockDate(iso: string, tz: string) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: tz }).format(new Date(iso));
}

function ManualEntry({
  open,
  onClose,
  tasks,
}: {
  open: boolean;
  onClose: () => void;
  tasks: Array<{ id: string; title: string }>;
}) {
  const { t } = useTranslation('time');
  const prefs = usePrefs();
  const today = useToday();
  const errorMessage = useErrorMessage();
  const invalidate = useInvalidatePlanning();
  const { categories, label } = useCategories();
  const now = clockOf(new Date(), prefs.timezone);
  const [form, setForm] = useState({
    date: today,
    start: '09:00',
    end: '10:00',
    description: '',
    taskId: '',
    categoryId: '',
    focus: false,
  });
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));
  const [warning, setWarning] = useState(false);
  const save = useMutation({
    mutationFn: () =>
      timeApi.createManual({
        started_at: zonedIso(form.date, form.start, prefs.timezone),
        ended_at: zonedIso(form.date, form.end, prefs.timezone),
        description: form.description.trim(),
        task_id: form.taskId || null,
        category_id: form.categoryId || null,
        is_focus: form.focus,
      }),
    onSuccess: (entry) => {
      if (entry.warnings?.length) setWarning(true);
      else onClose();
    },
    onSettled: invalidate,
  });
  const fieldErrors = save.error instanceof ApiError ? save.error.fieldErrors() : {};
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title={t('manual.title')}
      footer={
        warning ? (
          <Button onClick={onClose}>{t('manual.ok')}</Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              {t('manual.cancel')}
            </Button>
            <Button
              loading={save.isPending}
              disabled={form.end <= form.start}
              onClick={() => save.mutate()}
            >
              {t('manual.save')}
            </Button>
          </>
        )
      }
    >
      {warning ? (
        <Notice tone="warning">{t('manual.overlap')}</Notice>
      ) : (
        <>
          <TextField
            label={t('manual.date')}
            type="date"
            value={form.date}
            max={today}
            onChange={(e) => set('date', e.target.value)}
          />
          <div className={styles.formGrid}>
            <SelectField
              label={t('manual.start')}
              value={form.start}
              options={clockOptions(prefs.timeFormat, form.start)}
              onChange={(e) => set('start', e.target.value)}
            />
            <SelectField
              label={t('manual.end')}
              value={form.end}
              options={clockOptions(prefs.timeFormat, form.end)}
              onChange={(e) => set('end', e.target.value)}
              error={form.end <= form.start ? t('manual.endBeforeStart') : fieldErrors.ended_at}
            />
          </div>
          {form.date === today && form.end > now ? (
            <p className={styles.subtle}>{t('manual.futureHint')}</p>
          ) : null}
          <TextField
            label={t('manual.description')}
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
            maxLength={300}
          />
          <SelectField
            label={t('timer.task')}
            value={form.taskId}
            onChange={(e) => set('taskId', e.target.value)}
            options={[
              { value: '', label: t('timer.noTask') },
              ...tasks.map((x) => ({ value: x.id, label: x.title })),
            ]}
          />
          <SelectField
            label={t('manual.category')}
            value={form.categoryId}
            onChange={(e) => set('categoryId', e.target.value)}
            options={[
              { value: '', label: t('manual.noCategory') },
              ...categories.map((c) => ({ value: c.id, label: label(c) })),
            ]}
          />
          <label className={styles.toggle}>
            <input
              type="checkbox"
              checked={form.focus}
              onChange={(e) => set('focus', e.target.checked)}
            />
            {t('timer.focus')}
          </label>
          {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
        </>
      )}
    </Modal>
  );
}
