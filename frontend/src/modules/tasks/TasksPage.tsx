import { useMutation, useQuery } from '@tanstack/react-query';
import { CheckCheck, Inbox, ListTodo, Plus, Search, Sun } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useDeferredValue, useMemo, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router';

import { useInvalidatePlanning } from '@/modules/planning/hooks';
import { PRIORITY_RANK } from '@/modules/planning/meta';
import { keys, tasksApi, type TaskQuery } from '@/shared/api/planning';
import { PRIORITIES, type Task } from '@/shared/api/types';
import { Alert, EmptyState, PageHeader } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { useToday } from '@/shared/hooks/usePrefs';
import { addDays } from '@/shared/utils/datetime';

import { TaskDrawer } from './TaskDrawer';
import { TaskRow } from './TaskRow';
import styles from './tasks.module.css';

type View = 'open' | 'today' | 'inbox' | 'done';
const VIEWS: Array<{ key: View; icon: typeof ListTodo }> = [
  { key: 'open', icon: ListTodo },
  { key: 'today', icon: Sun },
  { key: 'inbox', icon: Inbox },
  { key: 'done', icon: CheckCheck },
];

function viewQuery(view: View, today: string): TaskQuery {
  switch (view) {
    case 'today':
      return { status: 'OPEN', due_to: today };
    case 'inbox':
      return { inbox: true, status: 'OPEN' };
    case 'done':
      return { status: 'COMPLETED,CANCELLED', ordering: '-created_at' };
    default:
      return { status: 'OPEN', ordering: 'due_at' };
  }
}

type GroupKey = 'overdue' | 'today' | 'tomorrow' | 'later' | 'noDate';

function groupTasks(tasks: Task[], today: string): Array<{ key: GroupKey; items: Task[] }> {
  const groups: Record<GroupKey, Task[]> = {
    overdue: [],
    today: [],
    tomorrow: [],
    later: [],
    noDate: [],
  };
  for (const task of tasks) {
    if (!task.due_date) groups.noDate.push(task);
    else if (task.is_overdue || task.due_date < today) groups.overdue.push(task);
    else if (task.due_date === today) groups.today.push(task);
    else if (task.due_date === addDays(today, 1)) groups.tomorrow.push(task);
    else groups.later.push(task);
  }
  const byPriority = (a: Task, b: Task) => PRIORITY_RANK[b.priority] - PRIORITY_RANK[a.priority];
  groups.today.sort(byPriority);
  groups.noDate.sort(byPriority);
  return (Object.keys(groups) as GroupKey[])
    .map((key) => ({ key, items: groups[key] }))
    .filter((g) => g.items.length);
}

export default function TasksPage({ inbox = false }: { inbox?: boolean }) {
  const { t } = useTranslation('tasks');
  const navigate = useNavigate();
  const location = useLocation();
  const { taskId } = useParams();
  const [search] = useSearchParams();
  const today = useToday();
  const invalidate = useInvalidatePlanning();
  const errorMessage = useErrorMessage();

  const backTo = (location.state as { from?: string } | null)?.from;
  const view: View = inbox ? 'inbox' : ((search.get('view') as View | null) ?? 'open');
  const [q, setQ] = useState('');
  const [priority, setPriority] = useState('');
  const [title, setTitle] = useState('');
  const deferredQ = useDeferredValue(q.trim());

  const query: TaskQuery = {
    ...viewQuery(view, today),
    q: deferredQ || undefined,
    priority: priority || undefined,
  };
  const list = useQuery({ queryKey: keys.taskList(query), queryFn: () => tasksApi.list(query) });
  const counts = useQuery({
    queryKey: keys.taskList({ inbox: true, status: 'OPEN', page_size: 1 }),
    queryFn: () => tasksApi.list({ inbox: true, status: 'OPEN', page_size: 1 }),
  });
  const tasks = useMemo(() => list.data?.results ?? [], [list.data]);
  const groups = useMemo(
    () => (view === 'open' || view === 'today' ? groupTasks(tasks, today) : null),
    [tasks, today, view],
  );

  const create = useMutation({
    mutationFn: (value: string) =>
      view === 'inbox'
        ? tasksApi.quick(value)
        : tasksApi.create({ title: value, due_date: view === 'today' ? today : undefined }),
    onSuccess: () => setTitle(''),
    onSettled: invalidate,
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const value = title.trim();
    if (value) create.mutate(value);
  };

  const listPath = inbox ? '/tasks/inbox' : `/tasks${location.search}`;
  const open = (task: Task) =>
    navigate(`/tasks/${task.id}`, { state: { from: taskId ? backTo : listPath } });
  const close = () => navigate(backTo ?? '/tasks', { replace: false });

  const viewHref = (key: View) =>
    key === 'inbox' ? '/tasks/inbox' : key === 'open' ? '/tasks' : `/tasks?view=${key}`;
  const inboxCount = counts.data?.count ?? 0;

  return (
    <div className={styles.page}>
      <PageHeader title={t('title')} description={t('subtitle')} />

      <nav className={styles.tabs} aria-label={t('title')}>
        {VIEWS.map(({ key, icon: Icon }) => (
          <Link
            key={key}
            to={viewHref(key)}
            className={styles.tab}
            aria-current={view === key ? 'page' : undefined}
          >
            {view === key ? <motion.span layoutId="tasks-tab" className={styles.tabBg} /> : null}
            <Icon size={16} />
            <span>{t(`views.${key}`)}</span>
            {key === 'inbox' && inboxCount ? <b className={styles.count}>{inboxCount}</b> : null}
          </Link>
        ))}
      </nav>

      <form className={styles.quickAdd} onSubmit={submit}>
        <Plus size={18} aria-hidden="true" />
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={
            view === 'inbox' ? t('quickAdd.inboxPlaceholder') : t('quickAdd.placeholder')
          }
          aria-label={t('quickAdd.label')}
          maxLength={300}
        />
        <button type="submit" disabled={!title.trim() || create.isPending}>
          {t('quickAdd.add')}
        </button>
      </form>
      {create.error ? <Alert>{errorMessage(create.error)}</Alert> : null}

      {view !== 'inbox' ? (
        <div className={styles.filters}>
          <label className={styles.search}>
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t('search')}
              aria-label={t('search')}
            />
          </label>
          <select
            className={styles.filterSelect}
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            aria-label={t('fields.priority')}
          >
            <option value="">{t('allPriorities')}</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {t(`priority.${p}`)}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <p className={styles.inboxHint}>{t('inboxHint')}</p>
      )}

      {list.error ? <Alert>{errorMessage(list.error)}</Alert> : null}

      {list.isLoading ? (
        <ul className={styles.list} aria-busy="true">
          {[0, 1, 2].map((i) => (
            <li key={i} className={styles.skeleton} />
          ))}
        </ul>
      ) : tasks.length === 0 ? (
        <EmptyState
          icon={
            <span className={styles.emptyIcon}>
              {view === 'done' ? <CheckCheck /> : view === 'inbox' ? <Inbox /> : <ListTodo />}
            </span>
          }
          title={t(`empty.${view}.title`)}
          description={t(`empty.${view}.description`)}
        />
      ) : groups ? (
        groups.map((group) => (
          <section key={group.key} className={styles.group} aria-labelledby={`group-${group.key}`}>
            <h2 id={`group-${group.key}`} data-tone={group.key}>
              {t(`groups.${group.key}`)}
              <span>{group.items.length}</span>
            </h2>
            <ul className={styles.list}>
              <AnimatePresence initial={false}>
                {group.items.map((task) => (
                  <TaskRow key={task.id} task={task} onOpen={open} />
                ))}
              </AnimatePresence>
            </ul>
          </section>
        ))
      ) : (
        <ul className={styles.list}>
          <AnimatePresence initial={false}>
            {tasks.map((task) => (
              <TaskRow key={task.id} task={task} onOpen={open} showInboxAction={view === 'inbox'} />
            ))}
          </AnimatePresence>
        </ul>
      )}

      <TaskDrawer taskId={taskId} onClose={close} />
    </div>
  );
}
