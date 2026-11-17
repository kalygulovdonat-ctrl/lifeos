import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Check, ChevronLeft, ChevronRight, Trash2, X } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useNavigate, useParams } from 'react-router';

import styles from '@/modules/growth.module.css';
import { ApiError } from '@/shared/api/client';
import { growthKeys, journalApi } from '@/shared/api/growth';
import { DAILY_SECTIONS, type JournalEntry } from '@/shared/api/types';
import { TextArea } from '@/shared/components/overlay';
import { Alert, Button, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { addDays, formatKey } from '@/shared/utils/datetime';

import j from './journal.module.css';

/** /journal/date/:date — the daily reflection of a day (created on first save). */
export function DailyPage() {
  const { date = '' } = useParams();
  const today = useToday();
  const entry = useQuery({
    queryKey: growthKeys.journalDay(date),
    queryFn: () =>
      journalApi.byDate(date).catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }),
  });
  if (entry.isLoading) return null;
  if (date > today) return <Navigate to={`/journal/date/${today}`} replace />;
  return <Editor key={date} mode="DAILY" date={date} entry={entry.data ?? undefined} />;
}

/** /journal/new and /journal/:entryId — a free entry. */
export function NotePage() {
  const { entryId } = useParams();
  const today = useToday();
  const entry = useQuery({
    queryKey: growthKeys.journalEntry(entryId ?? ''),
    queryFn: () => journalApi.get(entryId!),
    enabled: Boolean(entryId),
  });
  if (entryId && !entry.data) return entry.error ? <NotFoundNote /> : null;
  return (
    <Editor
      key={entry.data?.id ?? 'new'}
      mode="FREE"
      date={entry.data?.entry_date ?? today}
      entry={entry.data}
    />
  );
}

function NotFoundNote() {
  const { t } = useTranslation('journal');
  return <Alert>{t('notFound')}</Alert>;
}

function Editor({
  mode,
  date,
  entry,
}: {
  mode: 'DAILY' | 'FREE';
  date: string;
  entry?: JournalEntry;
}) {
  const { t } = useTranslation('journal');
  const prefs = usePrefs();
  const today = useToday();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const errorMessage = useErrorMessage();
  const [title, setTitle] = useState(entry?.title ?? '');
  const [body, setBody] = useState(entry?.body ?? '');
  const [entryDate, setEntryDate] = useState(entry?.entry_date ?? date);
  const [sections, setSections] = useState<Record<string, string>>(() => ({
    ...(entry?.sections ?? {}),
  }));
  const [saved, setSaved] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const refresh = () => void qc.invalidateQueries({ queryKey: growthKeys.journal });

  const save = useMutation({
    mutationFn: () => {
      const input =
        mode === 'DAILY'
          ? { entry_type: 'DAILY' as const, entry_date: date, sections, body, title }
          : { entry_type: 'FREE' as const, entry_date: entryDate, title, body };
      if (entry) {
        const { entry_type: _ignored, ...patch } = input;
        void _ignored;
        return journalApi.update(entry.id, patch);
      }
      return journalApi.create(input);
    },
    onSuccess: (saved_) => {
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
      if (!entry && mode === 'FREE') navigate(`/journal/${saved_.id}`, { replace: true });
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: () => journalApi.remove(entry!.id),
    onSuccess: () => {
      refresh();
      navigate('/journal');
    },
  });

  const dayLabel = formatKey(date, prefs.language, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
  const hasContent =
    mode === 'DAILY'
      ? Object.values(sections).some((v) => v.trim()) || body.trim()
      : body.trim() || title.trim();

  return (
    <div className={[styles.page, styles.narrow].join(' ')}>
      <Link to="/journal" className={styles.back}>
        <ArrowLeft size={15} /> {t('back')}
      </Link>
      <header className={j.head}>
        {mode === 'DAILY' ? (
          <div className={styles.row}>
            <Link
              to={`/journal/date/${addDays(date, -1)}`}
              className={styles.iconBtn}
              aria-label={t('daily.prev')}
            >
              <ChevronLeft size={18} />
            </Link>
            <div>
              <h1>{t('daily.title')}</h1>
              <p className={styles.muted}>
                {dayLabel.charAt(0).toLocaleUpperCase() + dayLabel.slice(1)}
              </p>
            </div>
            {date < today ? (
              <Link
                to={`/journal/date/${addDays(date, 1)}`}
                className={styles.iconBtn}
                aria-label={t('daily.next')}
              >
                <ChevronRight size={18} />
              </Link>
            ) : null}
          </div>
        ) : (
          <h1>{entry ? t('note.edit') : t('note.new')}</h1>
        )}
      </header>

      <div className={styles.panel}>
        {mode === 'FREE' ? (
          <div className={styles.formGrid}>
            <TextField
              label={t('note.title')}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              data-autofocus
            />
            <TextField
              label={t('note.date')}
              type="date"
              value={entryDate}
              max={today}
              onChange={(e) => setEntryDate(e.target.value)}
            />
          </div>
        ) : null}
        {mode === 'DAILY'
          ? DAILY_SECTIONS.map((key, i) => (
              <TextArea
                key={key}
                label={t(`sections.${key}`)}
                placeholder={t(`placeholders.${key}`)}
                value={sections[key] ?? ''}
                onChange={(e) => setSections((s) => ({ ...s, [key]: e.target.value }))}
                rows={2}
                maxLength={10000}
                {...(i === 0 ? { 'data-autofocus': true } : {})}
              />
            ))
          : null}
        <TextArea
          label={mode === 'DAILY' ? t('sections.notes') : t('note.body')}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={mode === 'DAILY' ? 3 : 12}
        />
        <p className={styles.subtle}>{mode === 'DAILY' ? t('daily.skipHint') : t('privacy')}</p>
        {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
        <div className={styles.row} style={{ justifyContent: 'space-between' }}>
          <div>
            {entry ? (
              confirmDelete ? (
                <span className={styles.row}>
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
                </span>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Trash2 size={15} />}
                  onClick={() => setConfirmDelete(true)}
                >
                  {t('delete')}
                </Button>
              )
            ) : null}
          </div>
          <Button
            loading={save.isPending}
            disabled={!hasContent}
            icon={saved ? <Check size={16} /> : undefined}
            onClick={() => save.mutate()}
          >
            {saved ? t('saved') : t('save')}
          </Button>
        </div>
      </div>
    </div>
  );
}
