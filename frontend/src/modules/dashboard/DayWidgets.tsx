import { useQuery } from '@tanstack/react-query';
import {
  ArrowUpRight,
  Brain,
  CalendarDays,
  CircleCheck,
  Flame,
  Hourglass,
  Inbox,
  ListTodo,
  Target,
  type LucideIcon,
} from 'lucide-react';
import { motion } from 'motion/react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { TIME_TYPE_META } from '@/modules/planning/meta';
import { TaskRow } from '@/modules/tasks/TaskRow';
import { dashboardApi, keys } from '@/shared/api/planning';
import type { DashboardData } from '@/shared/api/types';
import { CountUp } from '@/shared/components/motion';
import { riseChild, spotlight, staggerParent } from '@/shared/components/motion-utils';
import { Badge, IconTile } from '@/shared/components/ui';
import { useNow, usePrefs } from '@/shared/hooks/usePrefs';
import { formatTime } from '@/shared/utils/datetime';

import styles from './dashboard.module.css';

const TASK_LIMIT = 5;

function Widget({
  icon: Icon,
  title,
  to,
  action,
  wide,
  children,
  badge,
}: {
  icon: LucideIcon;
  title: string;
  to: string;
  action: string;
  wide?: boolean;
  badge?: ReactNode;
  children: ReactNode;
}) {
  return (
    <motion.div variants={riseChild} className={wide ? styles.wide : undefined}>
      <section className={styles.widget} onPointerMove={spotlight}>
        <span className={styles.widgetGlow} aria-hidden="true" />
        <div className={styles.widgetHead}>
          <span className={styles.widgetTitle}>
            <IconTile size={36}>
              <Icon size={17} />
            </IconTile>
            <h3>{title}</h3>
          </span>
          {badge}
        </div>
        <div className={styles.widgetBody}>{children}</div>
        <Link to={to} viewTransition className={styles.widgetLink}>
          {action}
          <ArrowUpRight size={15} aria-hidden="true" />
        </Link>
      </section>
    </motion.div>
  );
}

export function DayWidgets() {
  const { t } = useTranslation('dashboard');
  const data = useQuery({ queryKey: keys.dashboardDay(), queryFn: () => dashboardApi.get() });
  const d = data.data;

  return (
    <section aria-labelledby="today-title" className={styles.section}>
      <div className={styles.sectionHead}>
        <h2 id="today-title">{t('todayTitle')}</h2>
        <p>{t('dayHint')}</p>
      </div>
      {!d ? (
        <div className={styles.grid} aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={[styles.skeleton, i === 0 ? styles.wide : ''].join(' ')} />
          ))}
        </div>
      ) : (
        <motion.div
          className={styles.grid}
          variants={staggerParent}
          initial="hidden"
          animate="show"
        >
          <Widget
            icon={CalendarDays}
            title={t('widgets.schedule.title')}
            to="/schedule/day"
            action={t('openSchedule')}
            wide
          >
            <ScheduleList data={d} />
          </Widget>
          <Widget
            icon={ListTodo}
            title={t('widgets.tasks.title')}
            to="/tasks?view=today"
            action={t('openTasks')}
            badge={
              d.stats.tasks_total ? (
                <Badge tone="accent">
                  {d.stats.tasks_completed}/{d.stats.tasks_total}
                </Badge>
              ) : null
            }
          >
            <DayTasks data={d} />
          </Widget>
          <Widget
            icon={Hourglass}
            title={t('widgets.free.title')}
            to="/schedule/day"
            action={t('openSchedule')}
          >
            <FreeTime data={d} />
          </Widget>
          <Widget
            icon={Brain}
            title={t('widgets.focus.title')}
            to="/schedule/week"
            action={t('openSchedule')}
          >
            <Stats data={d} />
          </Widget>
          <Widget
            icon={Flame}
            title={t('widgets.habits.title')}
            to="/habits"
            action={t('openModule')}
            badge={<Badge tone="accent">Phase 2</Badge>}
          >
            <p className={styles.muted}>{t('widgets.habits.empty')}</p>
          </Widget>
          <Widget
            icon={Target}
            title={t('widgets.goals.title')}
            to="/goals"
            action={t('openModule')}
            badge={<Badge tone="accent">Phase 2</Badge>}
          >
            <p className={styles.muted}>{t('widgets.goals.empty')}</p>
          </Widget>
        </motion.div>
      )}
    </section>
  );
}

function ScheduleList({ data }: { data: DashboardData }) {
  const { t } = useTranslation('dashboard');
  const prefs = usePrefs();
  const now = useNow(60_000).getTime();
  const items = data.schedule.filter((e) => e.status !== 'CANCELLED');
  if (!items.length) {
    return (
      <div className={styles.emptyBlock}>
        <p>{t('widgets.schedule.none')}</p>
        <Link to="/schedule/day" className={styles.inlineCta}>
          {t('widgets.schedule.add')}
        </Link>
      </div>
    );
  }
  return (
    <ol className={styles.agenda}>
      {items.map((e) => {
        const start = Date.parse(e.start_at);
        const end = Date.parse(e.end_at);
        const state = end <= now ? 'past' : start <= now ? 'now' : 'next';
        const meta = TIME_TYPE_META[e.time_type];
        return (
          <li
            key={e.id ?? e.occurrence_key}
            data-state={state}
            style={{ ['--c' as string]: e.color ?? meta.color }}
          >
            <time>{formatTime(new Date(e.start_at), prefs)}</time>
            <i aria-hidden="true" />
            <span>
              <strong>{e.title}</strong>
              <small>
                {formatTime(new Date(e.start_at), prefs)} – {formatTime(new Date(e.end_at), prefs)}{' '}
                · {t(`schedule:timeType.${e.time_type}`)}
              </small>
            </span>
            {state === 'now' ? <em>{t('widgets.schedule.now')}</em> : null}
          </li>
        );
      })}
    </ol>
  );
}

function DayTasks({ data }: { data: DashboardData }) {
  const { t } = useTranslation('dashboard');
  const navigate = useNavigate();
  const tasks = [...data.tasks.overdue, ...data.tasks.today];
  const unique = tasks.filter((task, i) => tasks.findIndex((x) => x.id === task.id) === i);
  return (
    <>
      {unique.length ? (
        <ul className={styles.taskList}>
          {unique.slice(0, TASK_LIMIT).map((task) => (
            <TaskRow
              key={task.id}
              task={task}
              onOpen={(x) => navigate(`/tasks/${x.id}`, { state: { from: '/' } })}
            />
          ))}
        </ul>
      ) : (
        <div className={styles.emptyBlock}>
          <CircleCheck size={22} aria-hidden="true" />
          <p>{data.tasks.completed_count ? t('widgets.tasks.allDone') : t('widgets.tasks.none')}</p>
        </div>
      )}
      {data.inbox_count ? (
        <Link to="/tasks/inbox" className={styles.inboxLink}>
          <Inbox size={15} />
          {t('widgets.tasks.inbox', { count: data.inbox_count })}
        </Link>
      ) : null}
    </>
  );
}

function FreeTime({ data }: { data: DashboardData }) {
  const { t } = useTranslation('dashboard');
  const prefs = usePrefs();
  const f = data.free_time;
  const total = f.busy_minutes + f.free_minutes || 1;
  return (
    <>
      <p className={styles.bigNumber}>
        <CountUp
          value={f.free_minutes / 60}
          format={(n) => t('units.hours', { value: n.toFixed(1) })}
        />
      </p>
      <div className={styles.split} aria-hidden="true">
        <i style={{ width: `${(f.busy_minutes / total) * 100}%` }} />
      </div>
      <p className={styles.muted}>
        {t('widgets.free.busy', { busy: Math.round(f.busy_minutes / 6) / 10 })}
      </p>
      <ul className={styles.slots}>
        {f.slots.slice(0, 3).map((s) => (
          <li key={s.start_at}>
            {formatTime(new Date(s.start_at), prefs)} – {formatTime(new Date(s.end_at), prefs)}
          </li>
        ))}
      </ul>
    </>
  );
}

function Stats({ data }: { data: DashboardData }) {
  const { t } = useTranslation('dashboard');
  const s = data.stats;
  return (
    <dl className={styles.stats}>
      <div>
        <dt>{t('stats.focus')}</dt>
        <dd>
          <CountUp
            value={s.focus_minutes / 60}
            format={(n) => t('units.hours', { value: n.toFixed(1) })}
          />
        </dd>
      </div>
      <div>
        <dt>{t('stats.planned')}</dt>
        <dd>
          <CountUp
            value={s.planned_minutes / 60}
            format={(n) => t('units.hours', { value: n.toFixed(1) })}
          />
        </dd>
      </div>
      <div>
        <dt>{t('stats.done')}</dt>
        <dd>
          {s.tasks_completed}
          <small>/{s.tasks_total}</small>
        </dd>
      </div>
    </dl>
  );
}
