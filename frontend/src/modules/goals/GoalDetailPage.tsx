import { useMutation, useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  Check,
  Link2,
  Pencil,
  Plus,
  SkipForward,
  Sparkles,
  Trash2,
  Undo2,
  X,
} from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import styles from '@/modules/growth.module.css';
import { useInvalidatePlanning } from '@/modules/planning/hooks';
import { TaskRow } from '@/modules/tasks/TaskRow';
import { goalsApi, growthKeys } from '@/shared/api/growth';
import { keys, tasksApi } from '@/shared/api/planning';
import type { GoalAction, GoalDetail } from '@/shared/api/types';
import { Confetti, ProgressRing } from '@/shared/components/motion';
import { useCelebration } from '@/shared/components/motion-utils';
import { Notice } from '@/shared/components/overlay';
import { Alert, Button, PageHeader } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs } from '@/shared/hooks/usePrefs';
import { dateKey, formatKey, formatTime } from '@/shared/utils/datetime';

import { GoalEditor } from './GoalEditor';
import g from './goals.module.css';

const ACTIONS_BY_STATUS: Record<string, GoalAction[]> = {
  ACTIVE: ['COMPLETE', 'PAUSE', 'ABANDON'],
  PAUSED: ['RESUME', 'COMPLETE', 'ABANDON'],
  COMPLETED: ['REOPEN'],
  ABANDONED: ['REOPEN'],
};

export default function GoalDetailPage() {
  const { goalId = '' } = useParams();
  const { t } = useTranslation('goals');
  const navigate = useNavigate();
  const errorMessage = useErrorMessage();
  const invalidate = useInvalidatePlanning();
  const [editing, setEditing] = useState(false);
  const [childOpen, setChildOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const goal = useQuery({ queryKey: growthKeys.goal(goalId), queryFn: () => goalsApi.get(goalId) });
  const celebrate = useCelebration(
    goal.data ? goal.data.target_reached || goal.data.status === 'COMPLETED' : undefined,
  );
  const status = useMutation({
    mutationFn: (action: GoalAction) => goalsApi.status(goalId, action),
    onSettled: invalidate,
  });
  const remove = useMutation({
    mutationFn: () => goalsApi.remove(goalId),
    onSuccess: () => navigate('/goals'),
    onSettled: invalidate,
  });

  if (goal.error) return <Alert>{errorMessage(goal.error)}</Alert>;
  const d = goal.data;
  if (!d) return null;
  const pct = Number(d.progress_pct);

  return (
    <div className={[styles.page, styles.narrow].join(' ')}>
      <Link to="/goals" className={styles.back}>
        <ArrowLeft size={15} /> {t('back')}
      </Link>
      <PageHeader
        title={d.title}
        description={`${t(`level.${d.level}`)} · ${t(`progressType.${d.progress_type}`)} · ${t(`status.${d.status}`)}`}
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
              icon={<Plus size={15} />}
              onClick={() => setChildOpen(true)}
            >
              {t('addChild')}
            </Button>
          </div>
        }
      />

      {d.target_reached ? (
        <Notice tone="success" icon={<Sparkles size={16} />}>
          <strong>{t('reachedTitle')}</strong> {t('reachedHint')}{' '}
          <Button size="sm" onClick={() => status.mutate('COMPLETE')}>
            {t('action.COMPLETE')}
          </Button>
        </Notice>
      ) : null}

      <section className={[styles.panel, g.hero].join(' ')} aria-label={t('progressTitle')}>
        <ProgressRing value={pct / 100} size={140} stroke={11} tone="onLight">
          {celebrate ? <Confetti key={celebrate} /> : null}
          <div className={g.ringValue}>
            <strong>{Math.round(pct)}%</strong>
            <span>{t('progressTitle')}</span>
          </div>
        </ProgressRing>
        <div className={styles.stack} style={{ flex: 1, minWidth: 220 }}>
          {d.description ? <p className={styles.muted}>{d.description}</p> : null}
          <Dates goal={d} />
          {d.progress_type === 'METRIC' || d.progress_type === 'MANUAL' ? (
            <ProgressInput goal={d} />
          ) : null}
          <div className={styles.row}>
            {ACTIONS_BY_STATUS[d.status]?.map((action) => (
              <Button
                key={action}
                size="sm"
                variant={action === 'COMPLETE' ? 'primary' : 'secondary'}
                loading={status.isPending && status.variables === action}
                onClick={() => status.mutate(action)}
              >
                {t(`action.${action}`)}
              </Button>
            ))}
          </div>
          {status.error ? <Alert>{errorMessage(status.error)}</Alert> : null}
        </div>
      </section>

      {d.progress_type === 'MILESTONES' || d.milestones.length ? <Milestones goal={d} /> : null}
      <LinkedTasks goal={d} />
      <History goalId={d.id} />

      <div className={styles.row} style={{ justifyContent: 'flex-end' }}>
        {confirmDelete ? (
          <>
            <Button
              variant="ghost"
              size="sm"
              icon={<X size={15} />}
              onClick={() => setConfirmDelete(false)}
            >
              {t('keep')}
            </Button>
            <Button size="sm" loading={remove.isPending} onClick={() => remove.mutate()}>
              {t('confirmDelete')}
            </Button>
          </>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            icon={<Trash2 size={15} />}
            onClick={() => setConfirmDelete(true)}
          >
            {t('delete')}
          </Button>
        )}
      </div>

      <GoalEditor open={editing} onClose={() => setEditing(false)} goal={d} />
      <GoalEditor open={childOpen} onClose={() => setChildOpen(false)} parentId={d.id} />
    </div>
  );
}

function Dates({ goal }: { goal: GoalDetail }) {
  const { t } = useTranslation('goals');
  const prefs = usePrefs();
  const fmt = (key: string) =>
    formatKey(key, prefs.language, { day: 'numeric', month: 'long', year: 'numeric' });
  return (
    <p className={styles.subtle}>
      {t('dates', { start: fmt(goal.start_date) })}
      {goal.target_date ? ` → ${fmt(goal.target_date)}` : ''}
    </p>
  );
}

function ProgressInput({ goal }: { goal: GoalDetail }) {
  const { t } = useTranslation('goals');
  const invalidate = useInvalidatePlanning();
  const errorMessage = useErrorMessage();
  const [value, setValue] = useState(goal.current_value ? String(Number(goal.current_value)) : '');
  const save = useMutation({
    mutationFn: () => goalsApi.progress(goal.id, value),
    onSettled: invalidate,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (value !== '') save.mutate();
  };
  return (
    <form onSubmit={submit} className={styles.row}>
      <label className={styles.subtle} htmlFor="goal-progress">
        {goal.progress_type === 'MANUAL'
          ? t('progressInput.manual')
          : t('progressInput.metric', { unit: goal.metric_unit })}
      </label>
      <input
        id="goal-progress"
        type="number"
        step="any"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        style={{
          width: 110,
          height: 36,
          padding: '0 10px',
          borderRadius: 10,
          border: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          color: 'var(--color-text)',
          font: 'inherit',
        }}
      />
      <Button type="submit" size="sm" loading={save.isPending}>
        {t('progressInput.save')}
      </Button>
      {save.error ? (
        <span className={styles.subtle} style={{ color: 'var(--color-danger)' }}>
          {errorMessage(save.error)}
        </span>
      ) : null}
    </form>
  );
}

function Milestones({ goal }: { goal: GoalDetail }) {
  const { t } = useTranslation('goals');
  const prefs = usePrefs();
  const invalidate = useInvalidatePlanning();
  const [title, setTitle] = useState('');
  const [due, setDue] = useState('');
  const add = useMutation({
    mutationFn: () =>
      goalsApi.addMilestone(goal.id, { title: title.trim(), due_date: due || null }),
    onSuccess: () => {
      setTitle('');
      setDue('');
    },
    onSettled: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'PENDING' | 'COMPLETED' | 'SKIPPED' }) =>
      goalsApi.updateMilestone(id, { status }),
    onSettled: invalidate,
  });
  const remove = useMutation({ mutationFn: goalsApi.removeMilestone, onSettled: invalidate });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (title.trim()) add.mutate();
  };

  return (
    <section className={styles.panel} aria-labelledby="milestones-title">
      <h2 id="milestones-title">
        {t('milestones.title')}
        <span className={styles.chip}>
          {goal.milestones_done}/{goal.milestones_total}
        </span>
      </h2>
      {goal.milestones.length ? (
        <ul className={styles.list}>
          {goal.milestones.map((m) => (
            <li
              key={m.id}
              className={styles.item}
              style={m.status !== 'PENDING' ? { opacity: 0.7 } : undefined}
            >
              <span
                className={styles.chip}
                data-tone={
                  m.status === 'COMPLETED'
                    ? 'success'
                    : m.status === 'SKIPPED'
                      ? 'warning'
                      : undefined
                }
              >
                {t(`milestoneStatus.${m.status}`)}
              </span>
              <div className={styles.itemLink}>
                <strong
                  style={m.status === 'COMPLETED' ? { textDecoration: 'line-through' } : undefined}
                >
                  {m.title}
                </strong>
                {m.due_date ? (
                  <small>
                    {formatKey(m.due_date, prefs.language, { day: 'numeric', month: 'short' })}
                  </small>
                ) : null}
              </div>
              {m.status === 'PENDING' ? (
                <>
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={() => update.mutate({ id: m.id, status: 'COMPLETED' })}
                    aria-label={t('milestones.complete')}
                  >
                    <Check size={16} />
                  </button>
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={() => update.mutate({ id: m.id, status: 'SKIPPED' })}
                    aria-label={t('milestones.skip')}
                  >
                    <SkipForward size={15} />
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className={styles.iconBtn}
                  onClick={() => update.mutate({ id: m.id, status: 'PENDING' })}
                  aria-label={t('milestones.reopen')}
                >
                  <Undo2 size={15} />
                </button>
              )}
              <button
                type="button"
                className={styles.iconBtn}
                onClick={() => remove.mutate(m.id)}
                aria-label={t('milestones.delete')}
              >
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.muted}>{t('milestones.empty')}</p>
      )}
      <form onSubmit={submit} className={styles.row}>
        <input
          className={styles.grow}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('milestones.placeholder')}
          aria-label={t('milestones.placeholder')}
          maxLength={200}
          style={{
            height: 38,
            padding: '0 12px',
            borderRadius: 10,
            border: '1px dashed var(--color-border-strong)',
            background: 'transparent',
            color: 'var(--color-text)',
            font: 'inherit',
          }}
        />
        <input
          type="date"
          value={due}
          onChange={(e) => setDue(e.target.value)}
          aria-label={t('milestones.due')}
          style={{
            height: 38,
            padding: '0 10px',
            borderRadius: 10,
            border: '1px solid var(--color-border)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            font: 'inherit',
          }}
        />
        <Button
          type="submit"
          size="sm"
          icon={<Plus size={15} />}
          disabled={!title.trim()}
          loading={add.isPending}
        >
          {t('milestones.add')}
        </Button>
      </form>
    </section>
  );
}

function LinkedTasks({ goal }: { goal: GoalDetail }) {
  const { t } = useTranslation('goals');
  const navigate = useNavigate();
  const invalidate = useInvalidatePlanning();
  const linked = useQuery({
    queryKey: growthKeys.goalTasks(goal.id),
    queryFn: () => goalsApi.tasks(goal.id),
  });
  const q = { status: 'OPEN', ordering: 'due_at' };
  const open = useQuery({ queryKey: keys.taskList(q), queryFn: () => tasksApi.list(q) });
  const [pick, setPick] = useState('');
  const link = useMutation({
    mutationFn: (taskId: string) => goalsApi.linkTask(goal.id, taskId),
    onSuccess: () => setPick(''),
    onSettled: invalidate,
  });
  const unlink = useMutation({
    mutationFn: (taskId: string) => goalsApi.unlinkTask(goal.id, taskId),
    onSettled: invalidate,
  });
  const ids = new Set((linked.data ?? []).map((x) => x.id));
  const candidates = (open.data?.results ?? []).filter((x) => !ids.has(x.id));

  return (
    <section className={styles.panel} aria-labelledby="goal-tasks-title">
      <h2 id="goal-tasks-title">
        <Link2 size={15} /> {t('tasks.title')}
        <span className={styles.chip}>
          {goal.tasks_done}/{goal.tasks_total}
        </span>
      </h2>
      {goal.progress_type !== 'TASKS' ? (
        <p className={styles.subtle}>{t('tasks.notCounted')}</p>
      ) : null}
      {linked.data?.length ? (
        <ul className={styles.list}>
          {linked.data.map((task) => (
            <li key={task.id} className={styles.row} style={{ flexWrap: 'nowrap' }}>
              <ul className={[styles.list, styles.grow].join(' ')}>
                <TaskRow
                  task={task}
                  onOpen={(x) =>
                    navigate(`/tasks/${x.id}`, { state: { from: `/goals/${goal.id}` } })
                  }
                />
              </ul>
              <button
                type="button"
                className={styles.iconBtn}
                onClick={() => unlink.mutate(task.id)}
                aria-label={t('tasks.unlink')}
              >
                <X size={15} />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.muted}>{t('tasks.empty')}</p>
      )}
      <div className={styles.row}>
        <select
          value={pick}
          onChange={(e) => setPick(e.target.value)}
          aria-label={t('tasks.pick')}
          className={styles.grow}
          style={{
            height: 38,
            padding: '0 10px',
            borderRadius: 10,
            border: '1px solid var(--color-border)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            font: 'inherit',
          }}
        >
          <option value="">{t('tasks.pick')}</option>
          {candidates.map((x) => (
            <option key={x.id} value={x.id}>
              {x.title}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          variant="secondary"
          disabled={!pick}
          loading={link.isPending}
          onClick={() => link.mutate(pick)}
        >
          {t('tasks.link')}
        </Button>
      </div>
    </section>
  );
}

function History({ goalId }: { goalId: string }) {
  const { t } = useTranslation('goals');
  const prefs = usePrefs();
  const history = useQuery({
    queryKey: growthKeys.goalHistory(goalId),
    queryFn: () => goalsApi.history(goalId),
  });
  const rows = [
    ...(history.data?.progress ?? []).map((p) => ({
      at: p.recorded_at,
      text: t('history.progress', { pct: Math.round(Number(p.progress_pct)) }),
      note: p.note,
    })),
    ...(history.data?.status ?? []).map((s) => ({
      at: s.changed_at,
      text: s.from_status
        ? t('history.status', { to: t(`status.${s.to_status}`) })
        : t('history.created'),
      note: s.reason,
    })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  if (!rows.length) return null;
  return (
    <section className={styles.panel} aria-labelledby="goal-history-title">
      <h2 id="goal-history-title">{t('history.title')}</h2>
      <ul className={styles.list}>
        {rows.slice(0, 15).map((r, i) => (
          <li key={`${r.at}-${i}`} className={styles.row}>
            <span className={styles.subtle} style={{ width: 120 }}>
              {formatKey(dateKey(new Date(r.at), prefs.timezone), prefs.language, {
                day: 'numeric',
                month: 'short',
              })}
              , {formatTime(new Date(r.at), prefs)}
            </span>
            <span className={styles.grow}>
              {r.text}
              {r.note ? <span className={styles.subtle}> · {r.note}</span> : null}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
