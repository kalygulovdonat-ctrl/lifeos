import { useQuery } from '@tanstack/react-query';
import { CalendarDays, Plus, Target } from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import styles from '@/modules/growth.module.css';
import { goalsApi, growthKeys } from '@/shared/api/growth';
import type { Goal, GoalNode } from '@/shared/api/types';
import { Button, EmptyState, PageHeader } from '@/shared/components/ui';
import { usePrefs } from '@/shared/hooks/usePrefs';
import { formatKey } from '@/shared/utils/datetime';

import { GoalEditor } from './GoalEditor';
import g from './goals.module.css';

export function GoalProgressLine({ goal }: { goal: Goal }) {
  const { t } = useTranslation('goals');
  const pct = Number(goal.progress_pct);
  const detail =
    goal.progress_type === 'MILESTONES'
      ? t('detailLine.milestones', { done: goal.milestones_done, total: goal.milestones_total })
      : goal.progress_type === 'TASKS'
        ? t('detailLine.tasks', { done: goal.tasks_done, total: goal.tasks_total })
        : goal.progress_type === 'METRIC'
          ? `${Number(goal.current_value ?? goal.start_value)} / ${Number(goal.target_value)} ${goal.metric_unit}`
          : t('progressType.MANUAL');
  return (
    <div className={g.progress}>
      <div className={styles.bar} aria-hidden="true">
        <i style={{ width: `${pct}%` }} />
      </div>
      <span>
        <strong>{Math.round(pct)}%</strong> · {detail}
      </span>
    </div>
  );
}

function GoalCard({ node, depth }: { node: GoalNode; depth: number }) {
  const { t } = useTranslation('goals');
  const prefs = usePrefs();
  return (
    <li>
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <Link
          to={`/goals/${node.id}`}
          className={g.card}
          data-status={node.status}
          style={{ marginLeft: depth * 22 }}
        >
          <span className={g.level} data-level={node.level}>
            {t(`level.${node.level}`)}
          </span>
          <span className={g.title}>{node.title}</span>
          <span className={g.meta}>
            {node.status !== 'ACTIVE' ? (
              <span
                className={styles.chip}
                data-tone={node.status === 'COMPLETED' ? 'success' : 'warning'}
              >
                {t(`status.${node.status}`)}
              </span>
            ) : null}
            {node.target_reached ? (
              <span className={styles.chip} data-tone="success">
                {t('reached')}
              </span>
            ) : null}
            {node.target_date ? (
              <span className={styles.subtle}>
                <CalendarDays size={12} />{' '}
                {formatKey(node.target_date, prefs.language, {
                  day: 'numeric',
                  month: 'short',
                  year: 'numeric',
                })}
              </span>
            ) : null}
          </span>
          <GoalProgressLine goal={node} />
        </Link>
      </motion.div>
      {node.children.length ? (
        <ul className={g.tree}>
          {node.children.map((child) => (
            <GoalCard key={child.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export default function GoalsPage() {
  const { t } = useTranslation('goals');
  const [creating, setCreating] = useState(false);
  const tree = useQuery({ queryKey: growthKeys.goalTree(false), queryFn: () => goalsApi.tree() });
  const roots = tree.data ?? [];

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
      {tree.isLoading ? null : roots.length ? (
        <ul className={g.tree}>
          {roots.map((node) => (
            <GoalCard key={node.id} node={node} depth={0} />
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={<Target size={28} />}
          title={t('empty.title')}
          description={t('empty.description')}
          action={
            <Button icon={<Plus size={16} />} onClick={() => setCreating(true)}>
              {t('new')}
            </Button>
          }
        />
      )}
      <GoalEditor open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
