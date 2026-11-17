import { useMutation } from '@tanstack/react-query';
import { AlarmClock, CalendarDays, Inbox, ListChecks } from 'lucide-react';
import { motion } from 'motion/react';
import { useTranslation } from 'react-i18next';

import { PRIORITY_COLOR } from '@/modules/planning/meta';
import { useCategories, useInvalidatePlanning } from '@/modules/planning/hooks';
import { tasksApi } from '@/shared/api/planning';
import type { Task } from '@/shared/api/types';
import { CheckButton } from '@/shared/components/overlay';

import styles from './tasks.module.css';
import { useDueLabel } from './useDueLabel';

export function TaskRow({
  task,
  onOpen,
  showInboxAction = false,
}: {
  task: Task;
  onOpen: (task: Task) => void;
  showInboxAction?: boolean;
}) {
  const { t } = useTranslation('tasks');
  const { byId, label } = useCategories();
  const invalidate = useInvalidatePlanning();
  const dueLabel = useDueLabel();
  const done = task.status === 'COMPLETED';

  const toggle = useMutation({
    mutationFn: () => (done ? tasksApi.setStatus(task.id, 'TODO') : tasksApi.complete(task.id)),
    onSettled: invalidate,
  });
  const triage = useMutation({ mutationFn: () => tasksApi.triage(task.id), onSettled: invalidate });

  const category = task.category_id ? byId.get(task.category_id) : undefined;
  const due = dueLabel(task);
  const optimisticDone = toggle.isPending ? !done : done;

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: 24, transition: { duration: 0.18 } }}
      className={styles.row}
      data-done={optimisticDone || undefined}
      data-cancelled={task.status === 'CANCELLED' || undefined}
    >
      <CheckButton
        checked={optimisticDone}
        onChange={() => toggle.mutate()}
        label={done ? t('actions.reopen') : t('actions.complete')}
        disabled={task.status === 'CANCELLED'}
      />
      <button type="button" className={styles.rowMain} onClick={() => onOpen(task)}>
        <span className={styles.rowTitle}>{task.title}</span>
        <span className={styles.rowMeta}>
          {task.priority !== 'MEDIUM' ? (
            <span className={styles.priority} style={{ color: PRIORITY_COLOR[task.priority] }}>
              <i style={{ background: PRIORITY_COLOR[task.priority] }} />
              {t(`priority.${task.priority}`)}
            </span>
          ) : null}
          {due ? (
            <span className={styles.metaItem} data-overdue={task.is_overdue || undefined}>
              {task.is_overdue ? <AlarmClock size={13} /> : <CalendarDays size={13} />}
              {due}
            </span>
          ) : null}
          {task.subtasks_total ? (
            <span className={styles.metaItem}>
              <ListChecks size={13} />
              {task.subtasks_done}/{task.subtasks_total}
            </span>
          ) : null}
          {category ? (
            <span className={styles.metaItem}>
              <i className={styles.catDot} style={{ background: category.color }} />
              {label(category)}
            </span>
          ) : null}
          {task.status === 'IN_PROGRESS' ||
          task.status === 'POSTPONED' ||
          task.status === 'BACKLOG' ? (
            <span className={styles.statusChip} data-status={task.status}>
              {t(`status.${task.status}`)}
            </span>
          ) : null}
        </span>
      </button>
      {showInboxAction && task.in_inbox ? (
        <button
          type="button"
          className={styles.triage}
          onClick={() => triage.mutate()}
          disabled={triage.isPending}
          title={t('actions.triage')}
        >
          <Inbox size={15} />
          <span>{t('actions.triage')}</span>
        </button>
      ) : null}
    </motion.li>
  );
}
