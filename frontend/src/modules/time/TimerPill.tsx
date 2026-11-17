import { Pause, Timer } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { formatStopwatch, useTimer } from './useTimer';
import styles from './time.module.css';

/** Always-visible running timer, restored from the server after a reload (BR-056). */
export function TimerPill({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation('time');
  const { entry, seconds } = useTimer();
  return (
    <AnimatePresence>
      {entry ? (
        <motion.span
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
        >
          <Link
            to="/time"
            className={styles.pill}
            data-paused={entry.status === 'PAUSED' || undefined}
            data-compact={compact || undefined}
            aria-label={t('pill', { time: formatStopwatch(seconds) })}
          >
            {entry.status === 'PAUSED' ? (
              <Pause size={14} />
            ) : (
              <i className={styles.dot} aria-hidden="true" />
            )}
            <b>{formatStopwatch(seconds)}</b>
            {!compact ? (
              <span>{entry.task?.title ?? (entry.description || t('timer.untitled'))}</span>
            ) : null}
            {!compact ? <Timer size={14} aria-hidden="true" /> : null}
          </Link>
        </motion.span>
      ) : null}
    </AnimatePresence>
  );
}
