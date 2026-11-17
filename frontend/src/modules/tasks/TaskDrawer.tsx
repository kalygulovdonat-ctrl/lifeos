import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Archive,
  CalendarPlus,
  CircleSlash,
  Clock,
  History,
  Play,
  Redo2,
  RotateCcw,
  Square,
  Timer,
  Trash2,
  Undo2,
  X,
} from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { useCategories, useInvalidatePlanning } from '@/modules/planning/hooks';
import { ApiError } from '@/shared/api/client';
import { keys, tasksApi, type TaskInput } from '@/shared/api/planning';
import { PRIORITIES, type TaskDetail, type TaskStatus } from '@/shared/api/types';
import { CheckButton, Drawer, Modal, Notice, TextArea } from '@/shared/components/overlay';
import { Alert, Button, SelectField, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import {
  addDays,
  clockOptions,
  formatKey,
  formatTime,
  intlLocale,
  zonedIso,
} from '@/shared/utils/datetime';

import { formatStopwatch, useMinutesLabel, useTimer } from '@/modules/time/useTimer';

import styles from './tasks.module.css';

export function TaskDrawer({ taskId, onClose }: { taskId?: string; onClose: () => void }) {
  const { t } = useTranslation('tasks');
  const open = Boolean(taskId);
  const detail = useQuery({
    queryKey: keys.task(taskId ?? ''),
    queryFn: () => tasksApi.get(taskId!),
    enabled: open,
  });
  return (
    <Drawer open={open} onClose={onClose} title={t('drawerTitle')}>
      {detail.data ? (
        <TaskEditor
          key={detail.data.id + detail.data.updated_at}
          task={detail.data}
          onClose={onClose}
        />
      ) : detail.error ? (
        <Alert>{t('notFound')}</Alert>
      ) : (
        <div className={styles.drawerSkeleton} aria-busy="true" />
      )}
    </Drawer>
  );
}

function TaskEditor({ task, onClose }: { task: TaskDetail; onClose: () => void }) {
  const { t } = useTranslation('tasks');
  const fmtMinutes = useMinutesLabel();
  const errorMessage = useErrorMessage();
  const invalidate = useInvalidatePlanning();
  const { categories, label } = useCategories();
  const [form, setForm] = useState({
    title: task.title,
    description: task.description,
    priority: task.priority,
    category_id: task.category_id ?? '',
    due_date: task.due_date ?? '',
    estimated_minutes: task.estimated_minutes ? String(task.estimated_minutes) : '',
  });
  const [postponeOpen, setPostponeOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const dirty =
    form.title !== task.title ||
    form.description !== task.description ||
    form.priority !== task.priority ||
    form.category_id !== (task.category_id ?? '') ||
    form.due_date !== (task.due_date ?? '') ||
    form.estimated_minutes !== (task.estimated_minutes ? String(task.estimated_minutes) : '');

  const save = useMutation({
    mutationFn: () => {
      const patch: TaskInput = {
        title: form.title.trim(),
        description: form.description,
        priority: form.priority,
        category_id: form.category_id || null,
        estimated_minutes: form.estimated_minutes ? Number(form.estimated_minutes) : null,
      };
      if (form.due_date !== (task.due_date ?? '')) patch.due_date = form.due_date || null;
      return tasksApi.update(task.id, patch);
    },
    onSettled: invalidate,
  });
  const status = useMutation({
    mutationFn: (next: TaskStatus) =>
      next === 'COMPLETED' ? tasksApi.complete(task.id) : tasksApi.setStatus(task.id, next),
    onSettled: invalidate,
  });
  const archive = useMutation({
    mutationFn: () => (task.is_archived ? tasksApi.restore(task.id) : tasksApi.archive(task.id)),
    onSettled: invalidate,
  });
  const remove = useMutation({
    mutationFn: () => tasksApi.remove(task.id),
    onSuccess: onClose,
    onSettled: invalidate,
  });

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const done = task.status === 'COMPLETED';
  const error = save.error ?? status.error ?? archive.error ?? remove.error;
  const fieldErrors = save.error instanceof ApiError ? save.error.fieldErrors() : {};

  return (
    <>
      <div className={styles.editorHead}>
        <CheckButton
          size={28}
          checked={done}
          onChange={() => status.mutate(done ? 'TODO' : 'COMPLETED')}
          label={done ? t('actions.reopen') : t('actions.complete')}
          disabled={task.status === 'CANCELLED' || status.isPending}
        />
        <span className={styles.statusChip} data-status={task.status}>
          {t(`status.${task.status}`)}
        </span>
        {task.in_inbox ? <span className={styles.inboxChip}>{t('views.inbox')}</span> : null}
        {task.actual_minutes ? (
          <span className={styles.muted}>
            {t('actualTime', { time: fmtMinutes(task.actual_minutes) })}
          </span>
        ) : null}
        {task.postponed_count ? (
          <span className={styles.muted}>
            {t('postponedTimes', { count: task.postponed_count })}
          </span>
        ) : null}
      </div>

      {error ? <Alert>{errorMessage(error)}</Alert> : null}

      <TextField
        label={t('fields.title')}
        value={form.title}
        onChange={(e) => set('title', e.target.value)}
        error={fieldErrors.title}
        maxLength={300}
        data-autofocus
      />
      <TextArea
        label={t('fields.description')}
        value={form.description}
        onChange={(e) => set('description', e.target.value)}
        rows={3}
      />
      <div className={styles.formGrid}>
        <SelectField
          label={t('fields.priority')}
          value={form.priority}
          onChange={(e) => set('priority', e.target.value as typeof form.priority)}
          options={PRIORITIES.map((p) => ({ value: p, label: t(`priority.${p}`) }))}
        />
        <SelectField
          label={t('fields.category')}
          value={form.category_id}
          onChange={(e) => set('category_id', e.target.value)}
          options={[
            { value: '', label: t('fields.noCategory') },
            ...categories.map((c) => ({ value: c.id, label: label(c) })),
          ]}
        />
        <TextField
          label={t('fields.dueDate')}
          type="date"
          value={form.due_date}
          onChange={(e) => set('due_date', e.target.value)}
        />
        <TextField
          label={t('fields.estimate')}
          type="number"
          min={1}
          inputMode="numeric"
          value={form.estimated_minutes}
          onChange={(e) => set('estimated_minutes', e.target.value)}
          error={fieldErrors.estimated_minutes}
        />
      </div>
      {dirty ? (
        <div className={styles.saveRow}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              setForm({
                title: task.title,
                description: task.description,
                priority: task.priority,
                category_id: task.category_id ?? '',
                due_date: task.due_date ?? '',
                estimated_minutes: task.estimated_minutes ? String(task.estimated_minutes) : '',
              })
            }
          >
            {t('actions.discard')}
          </Button>
          <Button
            size="sm"
            loading={save.isPending}
            disabled={!form.title.trim()}
            onClick={() => save.mutate()}
          >
            {t('actions.save')}
          </Button>
        </div>
      ) : null}

      <div className={styles.actions}>
        {task.status === 'TODO' || task.status === 'BACKLOG' || task.status === 'POSTPONED' ? (
          <Button
            variant="secondary"
            size="sm"
            icon={<Play size={15} />}
            onClick={() => status.mutate('IN_PROGRESS')}
          >
            {t('actions.start')}
          </Button>
        ) : null}
        {task.status === 'IN_PROGRESS' ? (
          <Button
            variant="secondary"
            size="sm"
            icon={<Undo2 size={15} />}
            onClick={() => status.mutate('TODO')}
          >
            {t('actions.pause')}
          </Button>
        ) : null}
        {!done && task.status !== 'CANCELLED' ? (
          <>
            {task.status !== 'BACKLOG' ? (
              <Button
                variant="secondary"
                size="sm"
                icon={<Redo2 size={15} />}
                onClick={() => setPostponeOpen(true)}
              >
                {t('actions.postpone')}
              </Button>
            ) : null}
            <TimerButton taskId={task.id} />
            <Button
              variant="secondary"
              size="sm"
              icon={<CalendarPlus size={15} />}
              onClick={() => setScheduleOpen(true)}
            >
              {t('actions.schedule')}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon={<CircleSlash size={15} />}
              onClick={() => status.mutate('CANCELLED')}
            >
              {t('actions.cancel')}
            </Button>
          </>
        ) : null}
        {task.status === 'CANCELLED' ? (
          <Button
            variant="secondary"
            size="sm"
            icon={<RotateCcw size={15} />}
            onClick={() => status.mutate('TODO')}
          >
            {t('actions.restore')}
          </Button>
        ) : null}
      </div>

      <Subtasks task={task} />
      <HistoryList taskId={task.id} />

      <div className={styles.dangerRow}>
        <Button
          variant="ghost"
          size="sm"
          icon={<Archive size={15} />}
          onClick={() => archive.mutate()}
        >
          {task.is_archived ? t('actions.unarchive') : t('actions.archive')}
        </Button>
        {confirmDelete ? (
          <span className={styles.confirm}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setConfirmDelete(false)}
              icon={<X size={15} />}
            >
              {t('actions.keep')}
            </Button>
            <Button
              size="sm"
              className={styles.dangerButton}
              loading={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {t('actions.confirmDelete')}
            </Button>
          </span>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            icon={<Trash2 size={15} />}
            onClick={() => setConfirmDelete(true)}
          >
            {t('actions.delete')}
          </Button>
        )}
      </div>

      <PostponeDialog task={task} open={postponeOpen} onClose={() => setPostponeOpen(false)} />
      <ScheduleDialog task={task} open={scheduleOpen} onClose={() => setScheduleOpen(false)} />
    </>
  );
}

function TimerButton({ taskId }: { taskId: string }) {
  const { t } = useTranslation('tasks');
  const errorMessage = useErrorMessage();
  const timer = useTimer();
  const mine = timer.entry?.task_id === taskId;
  if (timer.entry && !mine) return null;
  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        icon={mine ? <Square size={14} /> : <Timer size={15} />}
        loading={timer.busy}
        onClick={() =>
          mine ? timer.stop.mutate() : timer.start.mutate({ task_id: taskId, is_focus: true })
        }
      >
        {mine
          ? t('actions.stopTimer', { time: formatStopwatch(timer.seconds) })
          : t('actions.startTimer')}
      </Button>
      {timer.error ? <span className={styles.muted}>{errorMessage(timer.error)}</span> : null}
    </>
  );
}

function Subtasks({ task }: { task: TaskDetail }) {
  const { t } = useTranslation('tasks');
  const invalidate = useInvalidatePlanning();
  const [title, setTitle] = useState('');
  const add = useMutation({
    mutationFn: (value: string) => tasksApi.addSubtask(task.id, value),
    onSuccess: () => setTitle(''),
    onSettled: invalidate,
  });
  const toggle = useMutation({
    mutationFn: ({ id, is_done }: { id: string; is_done: boolean }) =>
      tasksApi.updateSubtask(id, { is_done }),
    onSettled: invalidate,
  });
  const remove = useMutation({ mutationFn: tasksApi.removeSubtask, onSettled: invalidate });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (title.trim()) add.mutate(title.trim());
  };
  const doneCount = task.subtasks.filter((s) => s.is_done).length;

  return (
    <section className={styles.section} aria-labelledby="subtasks-title">
      <h3 id="subtasks-title">
        {t('subtasks.title')}
        {task.subtasks.length ? (
          <span>{t('subtasks.progress', { done: doneCount, total: task.subtasks.length })}</span>
        ) : null}
      </h3>
      {task.subtasks.length ? (
        <div className={styles.subProgress} aria-hidden="true">
          <i style={{ width: `${(doneCount / task.subtasks.length) * 100}%` }} />
        </div>
      ) : null}
      <ul className={styles.subtasks}>
        {task.subtasks.map((s) => {
          const checked =
            toggle.isPending && toggle.variables?.id === s.id
              ? toggle.variables.is_done
              : s.is_done;
          return (
            <li key={s.id} data-done={checked || undefined}>
              <CheckButton
                size={18}
                checked={checked}
                onChange={(v) => toggle.mutate({ id: s.id, is_done: v })}
                label={s.title}
              />
              <span>{s.title}</span>
              <button
                type="button"
                onClick={() => remove.mutate(s.id)}
                aria-label={t('actions.delete')}
              >
                <X size={14} />
              </button>
            </li>
          );
        })}
      </ul>
      <form onSubmit={submit} className={styles.subAdd}>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('subtasks.placeholder')}
          aria-label={t('subtasks.placeholder')}
          maxLength={300}
        />
      </form>
    </section>
  );
}

function HistoryList({ taskId }: { taskId: string }) {
  const { t } = useTranslation('tasks');
  const prefs = usePrefs();
  const history = useQuery({
    queryKey: keys.taskHistory(taskId),
    queryFn: () => tasksApi.history(taskId),
  });
  const items = [...(history.data ?? [])].reverse();
  if (!items.length) return null;
  const when = (iso: string) => {
    const d = new Date(iso);
    return `${new Intl.DateTimeFormat(intlLocale(prefs.language), { timeZone: prefs.timezone, day: 'numeric', month: 'short' }).format(d)}, ${formatTime(d, prefs)}`;
  };
  return (
    <section className={styles.section} aria-labelledby="history-title">
      <h3 id="history-title">
        <History size={15} /> {t('history.title')}
      </h3>
      <ol className={styles.history}>
        {items.map((h) => (
          <li key={h.id}>
            <span className={styles.historyDot} data-status={h.to_status} />
            <div>
              <strong>
                {h.from_status
                  ? t('history.changed', {
                      from: t(`status.${h.from_status}`),
                      to: t(`status.${h.to_status}`),
                    })
                  : t('history.created')}
              </strong>
              {h.reason ? <p>{t('history.reason', { reason: h.reason })}</p> : null}
              {h.from_status && h.new_due_at && h.new_due_at !== h.old_due_at ? (
                <p>{t('history.due', { date: when(h.new_due_at) })}</p>
              ) : null}
              <time dateTime={h.changed_at}>{when(h.changed_at)}</time>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function PostponeDialog({
  task,
  open,
  onClose,
}: {
  task: TaskDetail;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation('tasks');
  const invalidate = useInvalidatePlanning();
  const errorMessage = useErrorMessage();
  const today = useToday();
  const prefs = usePrefs();
  const [date, setDate] = useState(
    addDays(task.due_date && task.due_date >= today ? task.due_date : today, 1),
  );
  const [reason, setReason] = useState('');
  const postpone = useMutation({
    mutationFn: () => tasksApi.postpone(task.id, { new_due_date: date || null, reason }),
    onSuccess: onClose,
    onSettled: invalidate,
  });
  const quick = [1, 2, 7].map((n) => addDays(today, n));
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title={t('postpone.title')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t('actions.close')}
          </Button>
          <Button
            loading={postpone.isPending}
            disabled={!date && !reason.trim()}
            onClick={() => postpone.mutate()}
          >
            {t('postpone.submit')}
          </Button>
        </>
      }
    >
      <div className={styles.chips}>
        {quick.map((d, i) => (
          <button
            type="button"
            key={d}
            data-active={d === date || undefined}
            onClick={() => setDate(d)}
          >
            {i === 0
              ? t('due.tomorrow')
              : formatKey(d, prefs.language, { weekday: 'short', day: 'numeric', month: 'short' })}
          </button>
        ))}
      </div>
      <TextField
        label={t('postpone.newDate')}
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
      />
      <TextArea
        label={t('postpone.reason')}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
        placeholder={t('postpone.reasonHint')}
        maxLength={500}
      />
      {postpone.error ? <Alert>{errorMessage(postpone.error)}</Alert> : null}
    </Modal>
  );
}

function ScheduleDialog({
  task,
  open,
  onClose,
}: {
  task: TaskDetail;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation('tasks');
  const ts = useTranslation('schedule').t;
  const invalidate = useInvalidatePlanning();
  const errorMessage = useErrorMessage();
  const prefs = usePrefs();
  const today = useToday();
  const [date, setDate] = useState(task.due_date && task.due_date >= today ? task.due_date : today);
  const [start, setStart] = useState('10:00');
  const minutes = task.estimated_minutes ?? 60;
  const endDefault = (() => {
    const [h = 10, m = 0] = start.split(':').map(Number);
    const total = Math.min(h * 60 + m + minutes, 23 * 60 + 30);
    return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  })();
  const [end, setEnd] = useState<string | null>(null);
  const endValue = end ?? endDefault;
  const [conflict, setConflict] = useState<string[] | null>(null);
  const [done, setDone] = useState(false);

  const schedule = useMutation({
    mutationFn: (force: boolean) =>
      tasksApi.schedule(
        task.id,
        {
          start_at: zonedIso(date, start, prefs.timezone),
          end_at: zonedIso(date, endValue, prefs.timezone),
        },
        force,
      ),
    onSuccess: () => {
      setDone(true);
      setConflict(null);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'SCHEDULE_CONFLICT') {
        const items = (err.details.conflicting as Array<{ title: string }> | undefined) ?? [];
        setConflict(items.map((i) => i.title));
      }
    },
    onSettled: invalidate,
  });
  const options = clockOptions(prefs.timeFormat);
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="sm"
      title={t('scheduleBlock.title')}
      footer={
        done ? (
          <Button onClick={onClose}>{t('actions.close')}</Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              {t('actions.close')}
            </Button>
            {conflict ? (
              <Button loading={schedule.isPending} onClick={() => schedule.mutate(true)}>
                {ts('editor.saveAnyway')}
              </Button>
            ) : (
              <Button
                loading={schedule.isPending}
                disabled={endValue <= start}
                onClick={() => schedule.mutate(false)}
              >
                {t('scheduleBlock.submit')}
              </Button>
            )}
          </>
        )
      }
    >
      {done ? (
        <Notice tone="success" icon={<Clock size={16} />}>
          {t('scheduleBlock.created')}
        </Notice>
      ) : (
        <>
          <p className={styles.muted}>{t('scheduleBlock.hint', { title: task.title })}</p>
          <TextField
            label={t('scheduleBlock.date')}
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <div className={styles.formGrid}>
            <SelectField
              label={t('scheduleBlock.start')}
              value={start}
              onChange={(e) => {
                setStart(e.target.value);
                setEnd(null);
              }}
              options={options}
            />
            <SelectField
              label={t('scheduleBlock.end')}
              value={endValue}
              onChange={(e) => setEnd(e.target.value)}
              options={clockOptions(prefs.timeFormat, endValue)}
              error={endValue <= start ? ts('editor.endBeforeStart') : undefined}
            />
          </div>
          {conflict ? (
            <Notice tone="danger">
              <strong>{ts('editor.conflictTitle')}</strong> {conflict.join(', ')}
            </Notice>
          ) : null}
          {schedule.error && !conflict ? <Alert>{errorMessage(schedule.error)}</Alert> : null}
        </>
      )}
    </Modal>
  );
}
