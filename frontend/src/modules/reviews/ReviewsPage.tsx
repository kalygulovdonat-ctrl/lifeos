import { useMutation, useQuery } from '@tanstack/react-query';
import { CalendarCheck, ClipboardCheck, Star } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import styles from '@/modules/growth.module.css';
import { insightKeys, reviewsApi } from '@/shared/api/insight';
import { Alert, Button, EmptyState, PageHeader } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { addDays, formatKey, startOfWeek } from '@/shared/utils/datetime';

export default function ReviewsPage() {
  const { t } = useTranslation('reviews');
  const prefs = usePrefs();
  const today = useToday();
  const navigate = useNavigate();
  const errorMessage = useErrorMessage();
  const list = useQuery({ queryKey: insightKeys.reviews, queryFn: reviewsApi.list });
  const thisWeek = startOfWeek(today, prefs.weekStart);
  const lastWeek = addDays(thisWeek, -7);
  const start = useMutation({
    mutationFn: (week: string) => reviewsApi.start(week),
    onSuccess: (r) => navigate(`/reviews/${r.id}`),
  });
  const range = (from: string, to: string) =>
    `${formatKey(from, prefs.language, { day: 'numeric', month: 'short' })} – ${formatKey(to, prefs.language, { day: 'numeric', month: 'short', year: 'numeric' })}`;
  const items = list.data ?? [];
  const doneThis = items.find((r) => r.week_start === thisWeek);
  const doneLast = items.find((r) => r.week_start === lastWeek);

  return (
    <div className={[styles.page, styles.narrow].join(' ')}>
      <PageHeader title={t('title')} description={t('subtitle')} />
      <section className={styles.panel} aria-labelledby="start-title">
        <h2 id="start-title">
          <CalendarCheck size={16} /> {t('start.title')}
        </h2>
        <p className={styles.muted}>{t('start.hint')}</p>
        <div className={styles.row}>
          <Button
            loading={start.isPending && start.variables === thisWeek}
            onClick={() => start.mutate(thisWeek)}
          >
            {doneThis ? t('start.openThis') : t('start.this')}
          </Button>
          <Button
            variant="secondary"
            loading={start.isPending && start.variables === lastWeek}
            onClick={() => start.mutate(lastWeek)}
          >
            {doneLast ? t('start.openLast') : t('start.last')}
          </Button>
        </div>
        {start.error ? <Alert>{errorMessage(start.error)}</Alert> : null}
      </section>
      {list.isLoading ? null : items.length ? (
        <ul className={styles.list}>
          {items.map((r) => (
            <li key={r.id}>
              <Link to={`/reviews/${r.id}`} className={styles.item} style={{ color: 'inherit' }}>
                <span className={styles.itemLink}>
                  <strong>{range(r.week_start, r.week_end)}</strong>
                  <small>
                    {r.status === 'COMPLETED' ? t('status.COMPLETED') : t('status.DRAFT')}
                  </small>
                </span>
                {r.week_rating ? (
                  <span className={styles.chip} data-tone="accent">
                    <Star size={12} /> {r.week_rating}/10
                  </span>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={<ClipboardCheck size={28} />}
          title={t('empty.title')}
          description={t('empty.description')}
        />
      )}
    </div>
  );
}
