import { useQuery } from '@tanstack/react-query';
import { Lock, NotebookPen, PenLine, Search, Sunset } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import styles from '@/modules/growth.module.css';
import { growthKeys, journalApi } from '@/shared/api/growth';
import { DAILY_SECTIONS, type JournalEntry } from '@/shared/api/types';
import { Button, EmptyState, PageHeader } from '@/shared/components/ui';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { formatKey } from '@/shared/utils/datetime';

import j from './journal.module.css';

function entryPreview(entry: JournalEntry, max = 180): string {
  const text =
    entry.entry_type === 'DAILY'
      ? DAILY_SECTIONS.map((k) => entry.sections[k])
          .filter(Boolean)
          .join(' · ')
      : entry.body;
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text;
}

export default function JournalPage() {
  const { t } = useTranslation('journal');
  const prefs = usePrefs();
  const navigate = useNavigate();
  const today = useToday();
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const deferred = useDeferredValue(q.trim());
  const query = { q: deferred || undefined, type: type || undefined };
  const list = useQuery({
    queryKey: growthKeys.journalList(query),
    queryFn: () => journalApi.list(query),
  });
  const todayDaily = useQuery({
    queryKey: growthKeys.journalDay(today),
    queryFn: () => journalApi.byDate(today).catch(() => null),
  });
  const entries = list.data?.results ?? [];

  return (
    <div className={[styles.page, styles.narrow].join(' ')}>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <Button
            variant="secondary"
            icon={<PenLine size={16} />}
            onClick={() => navigate('/journal/new')}
          >
            {t('newNote')}
          </Button>
        }
      />

      <Link to={`/journal/date/${today}`} className={j.cta}>
        <span className={j.ctaIcon}>
          <Sunset size={22} />
        </span>
        <span>
          <strong>{todayDaily.data ? t('daily.continue') : t('daily.start')}</strong>
          <small>{t('daily.hint')}</small>
        </span>
      </Link>

      <div className={styles.row}>
        <label className={j.search}>
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t('search')}
            aria-label={t('search')}
          />
        </label>
        <div className={styles.pills} role="group" aria-label={t('filter')}>
          {['', 'DAILY', 'FREE'].map((v) => (
            <button
              key={v || 'all'}
              type="button"
              aria-pressed={type === v}
              onClick={() => setType(v)}
            >
              {v ? t(`type.${v}`) : t('all')}
            </button>
          ))}
        </div>
      </div>

      {list.isLoading ? null : entries.length ? (
        <ul className={styles.list}>
          {entries.map((e) => (
            <li key={e.id}>
              <Link
                to={e.entry_type === 'DAILY' ? `/journal/date/${e.entry_date}` : `/journal/${e.id}`}
                className={j.entry}
              >
                <span className={j.date}>
                  <b>{Number(e.entry_date.slice(8))}</b>
                  <span>{formatKey(e.entry_date, prefs.language, { month: 'short' })}</span>
                </span>
                <span className={j.entryMain}>
                  <strong>
                    {e.title || (e.entry_type === 'DAILY' ? t('daily.title') : t('untitled'))}
                    {e.is_sensitive ? <Lock size={12} aria-label={t('private')} /> : null}
                  </strong>
                  <small>{entryPreview(e) || t('empty.preview')}</small>
                </span>
                <span
                  className={styles.chip}
                  data-tone={e.entry_type === 'DAILY' ? 'accent' : undefined}
                >
                  {t(`type.${e.entry_type}`)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={<NotebookPen size={28} />}
          title={deferred ? t('empty.search') : t('empty.title')}
          description={deferred ? undefined : t('empty.description')}
        />
      )}
      <p className={styles.subtle}>
        <Lock size={12} /> {t('privacy')}
      </p>
    </div>
  );
}
