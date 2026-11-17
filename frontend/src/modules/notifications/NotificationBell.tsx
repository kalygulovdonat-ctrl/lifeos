import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCheck } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { insightKeys, notificationsApi, type AppNotification } from '@/shared/api/insight';
import { usePrefs } from '@/shared/hooks/usePrefs';
import { formatTime } from '@/shared/utils/datetime';

import styles from './notifications.module.css';

/** In-app notifications (ADR-020): polled, never pushed. */
export function NotificationBell({ align = 'left' }: { align?: 'left' | 'right' }) {
  const { t } = useTranslation('notifications');
  const prefs = usePrefs();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const unread = useQuery({
    queryKey: [...insightKeys.notifications, 'unread'],
    queryFn: notificationsApi.unread,
    refetchInterval: 60_000,
  });
  const list = useQuery({
    queryKey: [...insightKeys.notifications, 'list'],
    queryFn: notificationsApi.list,
    enabled: open,
  });
  const refresh = () => void qc.invalidateQueries({ queryKey: insightKeys.notifications });
  const read = useMutation({ mutationFn: notificationsApi.read, onSettled: refresh });
  const readAll = useMutation({ mutationFn: notificationsApi.readAll, onSettled: refresh });

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const count = unread.data?.count ?? 0;
  const text = (n: AppNotification) => {
    const p = { ...n.params } as Record<string, unknown>;
    if (typeof p.start_at === 'string') p.time = formatTime(new Date(p.start_at), prefs);
    if (Array.isArray(p.signals))
      p.signals = (p.signals as string[]).map((x) => t(`signal.${x}`)).join(', ');
    return t(`message.${n.message_key}`, { ...p, defaultValue: n.message_key });
  };
  const openItem = (n: AppNotification) => {
    if (!n.read_at) read.mutate(n.id);
    setOpen(false);
    if (n.link) navigate(n.link);
  };

  return (
    <div className={styles.wrap} ref={box}>
      <button
        type="button"
        className={styles.bell}
        onClick={() => setOpen((v) => !v)}
        aria-label={count ? t('labelUnread', { count }) : t('label')}
        aria-expanded={open}
      >
        <Bell size={18} />
        {count ? <b className={styles.dot}>{count > 9 ? '9+' : count}</b> : null}
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div
            className={styles.panel}
            data-align={align}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            role="dialog"
            aria-label={t('label')}
          >
            <div className={styles.head}>
              <strong>{t('label')}</strong>
              {count ? (
                <button type="button" onClick={() => readAll.mutate()}>
                  <CheckCheck size={14} /> {t('readAll')}
                </button>
              ) : null}
            </div>
            {list.data?.results.length ? (
              <ul>
                {list.data.results.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => openItem(n)}
                      data-unread={!n.read_at || undefined}
                    >
                      <span>{text(n)}</span>
                      <small>{formatTime(new Date(n.created_at), prefs)}</small>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.empty}>{list.isLoading ? '…' : t('empty')}</p>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
