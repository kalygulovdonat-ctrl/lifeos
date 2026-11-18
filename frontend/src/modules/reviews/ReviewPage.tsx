import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Check, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import styles from '@/modules/growth.module.css';
import { useInvalidatePlanning } from '@/modules/planning/hooks';
import { insightKeys, reviewsApi, type Review, type ReviewDecision } from '@/shared/api/insight';
import { Confetti } from '@/shared/components/motion';
import { useCelebration } from '@/shared/components/motion-utils';
import { TextArea } from '@/shared/components/overlay';
import { Alert, Button, PageHeader } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs } from '@/shared/hooks/usePrefs';
import { addDays, formatKey, zonedIso } from '@/shared/utils/datetime';

import r from './reviews.module.css';

const STEPS = ['stats', 'tasks', 'reflect', 'finish'] as const;
const DECISIONS: ReviewDecision[] = ['KEEP', 'CARRY_OVER', 'RESCHEDULE', 'BACKLOG', 'CANCEL'];
const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`;

export default function ReviewPage() {
  const { reviewId = '' } = useParams();
  const { t } = useTranslation('reviews');
  const prefs = usePrefs();
  const errorMessage = useErrorMessage();
  const review = useQuery({
    queryKey: insightKeys.review(reviewId),
    queryFn: () => reviewsApi.get(reviewId),
  });
  const [step, setStep] = useState(0);
  const celebrate = useCelebration(review.data ? review.data.status === 'COMPLETED' : undefined);

  if (review.error) return <Alert>{errorMessage(review.error)}</Alert>;
  const d = review.data;
  if (!d) return null;
  const locked = d.status === 'COMPLETED';
  const range = `${formatKey(d.week_start, prefs.language, { day: 'numeric', month: 'long' })} – ${formatKey(d.week_end, prefs.language, { day: 'numeric', month: 'long' })}`;

  return (
    <div className={[styles.page, styles.narrow].join(' ')}>
      <Link to="/reviews" className={styles.back}>
        <ArrowLeft size={15} /> {t('back')}
      </Link>
      <PageHeader
        title={t('weekTitle')}
        description={`${range}${locked ? ` · ${t('status.COMPLETED')}` : ''}`}
      />
      {celebrate ? (
        <span className={r.confetti}>
          <Confetti key={celebrate} pieces={40} />
        </span>
      ) : null}
      {locked ? (
        <>
          <Stats review={d} />
          <Reflection review={d} locked />
        </>
      ) : (
        <>
          <ol className={r.steps}>
            {STEPS.map((s, i) => (
              <li key={s}>
                <button
                  type="button"
                  aria-current={i === step ? 'step' : undefined}
                  data-done={i < step || undefined}
                  onClick={() => setStep(i)}
                >
                  <b>{i + 1}</b> {t(`steps.${s}`)}
                </button>
              </li>
            ))}
          </ol>
          {step === 0 ? <Stats review={d} /> : null}
          {step === 1 ? <Decisions review={d} /> : null}
          {step === 2 ? <Reflection review={d} /> : null}
          {step === 3 ? <Finish review={d} /> : null}
          <div className={styles.row} style={{ justifyContent: 'space-between' }}>
            <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>
              {t('prev')}
            </Button>
            {step < STEPS.length - 1 ? (
              <Button onClick={() => setStep(step + 1)}>{t('next')}</Button>
            ) : (
              <span />
            )}
          </div>
        </>
      )}
    </div>
  );
}

function Stats({ review }: { review: Review }) {
  const { t } = useTranslation('reviews');
  const qc = useQueryClient();
  const s = review.stats_snapshot;
  const refresh = useMutation({
    mutationFn: () => reviewsApi.refresh(review.id),
    onSuccess: (data) => qc.setQueryData(insightKeys.review(review.id), data),
  });
  return (
    <section className={styles.panel} aria-labelledby="stats-title">
      <div className={styles.panelHead}>
        <h2 id="stats-title">{t('stats.title')}</h2>
        {review.status === 'DRAFT' ? (
          <Button
            size="sm"
            variant="ghost"
            icon={<RefreshCw size={14} />}
            loading={refresh.isPending}
            onClick={() => refresh.mutate()}
          >
            {t('stats.refresh')}
          </Button>
        ) : null}
      </div>
      <dl className={styles.stats}>
        <div className={styles.stat}>
          <dt>{t('stats.tasks')}</dt>
          <dd>
            {pct(s.tasks?.completion_rate?.value)}
            <small> · {s.tasks?.completed ?? 0}</small>
          </dd>
        </div>
        <div className={styles.stat}>
          <dt>{t('stats.habits')}</dt>
          <dd>{pct(s.habits?.consistency?.value)}</dd>
        </div>
        <div className={styles.stat}>
          <dt>{t('stats.focus')}</dt>
          <dd>{t('hours', { value: (s.time?.focus_hours?.value ?? 0).toFixed(1) })}</dd>
        </div>
        <div className={styles.stat}>
          <dt>{t('stats.accuracy')}</dt>
          <dd>{pct(s.time?.schedule_accuracy?.value)}</dd>
        </div>
      </dl>
      <p className={styles.subtle}>
        {review.status === 'DRAFT'
          ? t('stats.draftHint')
          : t('stats.frozenHint', { version: review.formula_version })}
      </p>
    </section>
  );
}

function Decisions({ review }: { review: Review }) {
  const { t } = useTranslation('reviews');
  const ts = useTranslation('tasks').t;
  const prefs = usePrefs();
  const qc = useQueryClient();
  const errorMessage = useErrorMessage();
  const tasks = useQuery({
    queryKey: insightKeys.reviewTasks(review.id),
    queryFn: () => reviewsApi.tasks(review.id),
  });
  const initial = Object.fromEntries(review.decisions.map((d) => [d.task_id, d]));
  const [choice, setChoice] = useState<Record<string, { decision: ReviewDecision; date: string }>>(
    () =>
      Object.fromEntries(
        review.decisions.map((d) => [
          d.task_id,
          { decision: d.decision, date: d.new_due_at?.slice(0, 10) ?? addDays(review.week_end, 3) },
        ]),
      ),
  );
  const save = useMutation({
    mutationFn: () =>
      reviewsApi.decide(
        review.id,
        Object.entries(choice)
          .filter(([, v]) => v.decision !== 'KEEP')
          .map(([task_id, v]) => ({
            task_id,
            decision: v.decision,
            new_due_at:
              v.decision === 'RESCHEDULE' ? zonedIso(v.date, '23:59', prefs.timezone) : null,
          })),
      ),
    onSuccess: (data) => qc.setQueryData(insightKeys.review(review.id), data),
  });
  const list = tasks.data ?? [];
  void initial;

  return (
    <section className={styles.panel} aria-labelledby="decide-title">
      <h2 id="decide-title">{t('tasks.title')}</h2>
      <p className={styles.muted}>{t('tasks.hint')}</p>
      {list.length ? (
        <ul className={styles.list}>
          {list.map((task) => {
            const c = choice[task.id] ?? {
              decision: 'KEEP' as ReviewDecision,
              date: addDays(review.week_end, 3),
            };
            return (
              <li key={task.id} className={r.decision}>
                <div className={styles.itemLink}>
                  <strong>{task.title}</strong>
                  <small>
                    {ts(`status.${task.status}`)}
                    {task.due_date
                      ? ` · ${formatKey(task.due_date, prefs.language, { day: 'numeric', month: 'short' })}`
                      : ''}
                  </small>
                </div>
                <div className={styles.pills} role="radiogroup" aria-label={task.title}>
                  {DECISIONS.map((d) => (
                    <button
                      key={d}
                      type="button"
                      role="radio"
                      aria-checked={c.decision === d}
                      onClick={() => setChoice((x) => ({ ...x, [task.id]: { ...c, decision: d } }))}
                    >
                      {t(`decision.${d}`)}
                    </button>
                  ))}
                </div>
                {c.decision === 'RESCHEDULE' ? (
                  <input
                    type="date"
                    className={r.date}
                    value={c.date}
                    aria-label={t('tasks.newDate')}
                    onChange={(e) =>
                      setChoice((x) => ({ ...x, [task.id]: { ...c, date: e.target.value } }))
                    }
                  />
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className={styles.empty}>{t('tasks.none')}</p>
      )}
      {list.length ? (
        <div className={styles.row}>
          <Button
            size="sm"
            loading={save.isPending}
            onClick={() => save.mutate()}
            icon={save.isSuccess ? <Check size={14} /> : undefined}
          >
            {save.isSuccess ? t('saved') : t('tasks.save')}
          </Button>
          <span className={styles.subtle}>{t('tasks.appliedOnFinish')}</span>
        </div>
      ) : null}
      {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
    </section>
  );
}

const FIELDS = ['wins', 'challenges', 'lessons', 'next_week_focus'] as const;

function Reflection({ review, locked = false }: { review: Review; locked?: boolean }) {
  const { t } = useTranslation('reviews');
  const qc = useQueryClient();
  const errorMessage = useErrorMessage();
  const [form, setForm] = useState(() => ({
    wins: review.wins,
    challenges: review.challenges,
    lessons: review.lessons,
    next_week_focus: review.next_week_focus,
    week_rating: review.week_rating,
  }));
  const save = useMutation({
    mutationFn: () => reviewsApi.update(review.id, form),
    onSuccess: (data) => qc.setQueryData(insightKeys.review(review.id), data),
  });
  return (
    <section className={styles.panel} aria-labelledby="reflect-title">
      <h2 id="reflect-title">{t('reflect.title')}</h2>
      {FIELDS.map((f) =>
        locked ? (
          form[f] ? (
            <div key={f}>
              <p className={styles.subtle}>{t(`reflect.${f}`)}</p>
              <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{form[f]}</p>
            </div>
          ) : null
        ) : (
          <TextArea
            key={f}
            label={t(`reflect.${f}`)}
            placeholder={t(`reflect.placeholders.${f}`)}
            value={form[f]}
            rows={2}
            onChange={(e) => setForm((x) => ({ ...x, [f]: e.target.value }))}
          />
        ),
      )}
      <div>
        <p className={styles.subtle}>{t('reflect.rating')}</p>
        <div className={styles.pills} role="radiogroup" aria-label={t('reflect.rating')}>
          {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={form.week_rating === n}
              disabled={locked}
              onClick={() => setForm((x) => ({ ...x, week_rating: n }))}
              style={{ width: 36, padding: 0 }}
            >
              {n}
            </button>
          ))}
        </div>
      </div>
      {!locked ? (
        <div className={styles.row}>
          <Button
            size="sm"
            loading={save.isPending}
            onClick={() => save.mutate()}
            icon={save.isSuccess ? <Check size={14} /> : undefined}
          >
            {save.isSuccess ? t('saved') : t('reflect.save')}
          </Button>
        </div>
      ) : null}
      {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
    </section>
  );
}

function Finish({ review }: { review: Review }) {
  const { t } = useTranslation('reviews');
  const qc = useQueryClient();
  const invalidate = useInvalidatePlanning();
  const errorMessage = useErrorMessage();
  const complete = useMutation({
    mutationFn: () => reviewsApi.complete(review.id),
    onSuccess: (data) => {
      qc.setQueryData(insightKeys.review(review.id), data);
      void qc.invalidateQueries({ queryKey: insightKeys.reviews });
    },
    onSettled: invalidate,
  });
  return (
    <section className={styles.panel} aria-labelledby="finish-title">
      <h2 id="finish-title">{t('finish.title')}</h2>
      <p className={styles.muted}>{t('finish.hint', { count: review.decisions.length })}</p>
      <div className={styles.row}>
        <Button
          loading={complete.isPending}
          icon={<Check size={16} />}
          onClick={() => complete.mutate()}
        >
          {t('finish.button')}
        </Button>
      </div>
      {complete.error ? <Alert>{errorMessage(complete.error)}</Alert> : null}
    </section>
  );
}
