import { useQuery } from '@tanstack/react-query';
import type { TFunction } from 'i18next';
import { ArrowDownRight, ArrowUpRight, ChevronLeft, ChevronRight, Info } from 'lucide-react';
import { motion } from 'motion/react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useParams, useSearchParams } from 'react-router';

import styles from '@/modules/growth.module.css';
import { useCategories } from '@/modules/planning/hooks';
import { useMinutesLabel } from '@/modules/time/useTimer';
import {
  analyticsApi,
  insightKeys,
  type AnalyticsSummary,
  type Metric,
} from '@/shared/api/insight';
import { ColumnChart, ShareBars } from '@/shared/components/charts';
import { CountUp } from '@/shared/components/motion';
import { riseChild, staggerParent } from '@/shared/components/motion-utils';
import { Alert, PageHeader } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { addDays, addMonths, formatKey } from '@/shared/utils/datetime';

import a from './analytics.module.css';

const PERIODS = ['day', 'week', 'month'] as const;
type Period = (typeof PERIODS)[number];

/** A percentage that counts up to its value when the tile appears. */
const pctCount = (v: number | null | undefined) =>
  v === null || v === undefined ? (
    '—'
  ) : (
    <CountUp value={Math.round(v * 100)} format={(n) => `${Math.round(n)}%`} />
  );

function Delta({
  now,
  before,
  unit = 'pp',
}: {
  now: number | null;
  before: number | null | undefined;
  unit?: 'pp' | 'h';
}) {
  const { t } = useTranslation('analytics');
  if (now === null || before === null || before === undefined) return null;
  const diff =
    unit === 'pp' ? Math.round((now - before) * 100) : Math.round((now - before) * 10) / 10;
  if (diff === 0) return <span className={a.delta}>{t('delta.same')}</span>;
  const up = diff > 0;
  return (
    <span className={a.delta} data-dir={up ? 'up' : 'down'}>
      {up ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
      {up ? '+' : ''}
      {diff}
      {unit === 'pp' ? t('delta.pp') : t('delta.h')}
    </span>
  );
}

function Tile({
  title,
  metric,
  detail,
  hint,
  delta,
}: {
  title: string;
  metric: React.ReactNode;
  detail?: string;
  hint: string;
  delta?: React.ReactNode;
}) {
  return (
    <motion.div variants={riseChild} className={a.tile}>
      <span className={a.tileTitle}>{title}</span>
      <strong className={a.tileValue}>{metric}</strong>
      <span className={a.tileDetail}>
        {detail}
        {delta}
      </span>
      <details className={a.formula}>
        <summary>
          <Info size={12} /> {hint.split('|')[0]}
        </summary>
        <p>{hint.split('|')[1]}</p>
      </details>
    </motion.div>
  );
}

function ratio(m: Metric, t: TFunction<'analytics'>) {
  return m.value === null ? t('noData') : t('ratio', { n: m.numerator, d: m.denominator });
}

export default function AnalyticsPage() {
  const { period: raw = 'week' } = useParams();
  const [search, setSearch] = useSearchParams();
  const { t } = useTranslation('analytics');
  const prefs = usePrefs();
  const today = useToday();
  const errorMessage = useErrorMessage();
  const period = raw as Period;
  const date = search.get('date') ?? today;
  const query = useQuery({
    queryKey: insightKeys.analytics(period, date),
    queryFn: () => analyticsApi.get(period, date),
    placeholderData: (prev) => prev,
    enabled: PERIODS.includes(period),
  });
  if (!PERIODS.includes(period)) return <Navigate to="/analytics/week" replace />;

  const shift = (dir: 1 | -1) =>
    period === 'day'
      ? addDays(date, dir)
      : period === 'week'
        ? addDays(date, 7 * dir)
        : addMonths(date, dir);
  const go = (d: string) => setSearch(d === today ? {} : { date: d });
  const s = query.data;
  const heading = !s
    ? ''
    : period === 'day'
      ? formatKey(s.from, prefs.language, { weekday: 'long', day: 'numeric', month: 'long' })
      : period === 'month'
        ? formatKey(s.from, prefs.language, { month: 'long', year: 'numeric' })
        : `${formatKey(s.from, prefs.language, { day: 'numeric', month: 'short' })} – ${formatKey(s.to, prefs.language, { day: 'numeric', month: 'short' })}`;

  return (
    <div className={styles.page}>
      <PageHeader title={t('title')} description={t('subtitle')} />
      <div className={a.toolbar}>
        <div className={styles.row}>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => go(shift(-1))}
            aria-label={t('prev')}
          >
            <ChevronLeft size={18} />
          </button>
          <h2 className={a.heading}>{heading.charAt(0).toLocaleUpperCase() + heading.slice(1)}</h2>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => go(shift(1))}
            disabled={date >= today}
            aria-label={t('next')}
          >
            <ChevronRight size={18} />
          </button>
          {s ? (
            <span className={styles.chip} data-tone={s.is_final ? 'success' : 'accent'}>
              {s.is_final ? t('final') : t('live')}
            </span>
          ) : null}
        </div>
        <nav className={styles.pills} aria-label={t('periodLabel')}>
          {PERIODS.map((p) => (
            <Link
              key={p}
              to={`/analytics/${p}${search.get('date') ? `?date=${date}` : ''}`}
              aria-current={p === period ? 'page' : undefined}
            >
              {t(`periods.${p}`)}
            </Link>
          ))}
        </nav>
      </div>
      {query.error ? <Alert>{errorMessage(query.error)}</Alert> : null}
      {s ? <Report s={s} /> : null}
    </div>
  );
}

function Report({ s }: { s: AnalyticsSummary }) {
  const { t } = useTranslation('analytics');
  const prefs = usePrefs();
  const fmtMinutes = useMinutesLabel();
  const { byId, label } = useCategories();
  const tcr = s.tasks.completion_rate;
  const hc = s.habits.consistency;
  const acc = s.time.schedule_accuracy;
  const focus = s.time.focus_hours.value ?? 0;
  const dayTitle = (d: string) =>
    formatKey(d, prefs.language, { weekday: 'long', day: 'numeric', month: 'long' });
  const dayLabel = (d: string) =>
    s.period === 'week'
      ? formatKey(d, prefs.language, { weekday: 'short' })
      : String(Number(d.slice(8)));

  return (
    <>
      <motion.div
        className={a.tiles}
        variants={staggerParent}
        initial="hidden"
        animate="show"
        key={s.from}
      >
        <Tile
          title={t('tiles.tasks')}
          metric={pctCount(tcr.value)}
          detail={ratio(tcr, t)}
          hint={t('formulas.tasks')}
          delta={<Delta now={tcr.value} before={s.previous?.task_completion_rate} />}
        />
        <Tile
          title={t('tiles.habits')}
          metric={pctCount(hc.value)}
          detail={ratio(hc, t)}
          hint={t('formulas.habits')}
          delta={<Delta now={hc.value} before={s.previous?.habit_consistency} />}
        />
        <Tile
          title={t('tiles.focus')}
          metric={<CountUp value={focus} format={(n) => t('hours', { value: n.toFixed(1) })} />}
          detail={t('tracked', { value: s.time.tracked_hours.toFixed(1) })}
          hint={t('formulas.focus')}
          delta={<Delta now={focus} before={s.previous?.focus_hours} unit="h" />}
        />
        <Tile
          title={t('tiles.accuracy')}
          metric={pctCount(acc.value)}
          detail={
            acc.value === null
              ? t('noData')
              : t('accuracyDetail', {
                  done: fmtMinutes(acc.numerator ?? 0),
                  plan: fmtMinutes(acc.denominator ?? 0),
                })
          }
          hint={t('formulas.accuracy')}
        />
      </motion.div>

      {s.series.length ? (
        <div className={a.charts}>
          <section className={styles.panel} aria-labelledby="chart-tasks">
            <h3 id="chart-tasks">{t('charts.tasks')}</h3>
            <ColumnChart
              ariaLabel={t('charts.tasks')}
              tableLabel={t('charts.tasks')}
              format={(v) => String(Math.round(v))}
              data={s.series.map((d) => ({
                key: d.date,
                label: dayLabel(d.date),
                title: dayTitle(d.date),
                value: d.tasks_completed,
              }))}
            />
          </section>
          <section className={styles.panel} aria-labelledby="chart-focus">
            <h3 id="chart-focus">{t('charts.focus')}</h3>
            <ColumnChart
              ariaLabel={t('charts.focus')}
              tableLabel={t('charts.focus')}
              format={(v) => t('hours', { value: v.toFixed(1) })}
              data={s.series.map((d) => ({
                key: d.date,
                label: dayLabel(d.date),
                title: dayTitle(d.date),
                value: d.focus_minutes / 60,
              }))}
            />
          </section>
        </div>
      ) : null}

      <div className={styles.split}>
        <section className={styles.panel} aria-labelledby="dist-title">
          <h3 id="dist-title">{t('distribution.title')}</h3>
          {s.time.distribution.length ? (
            <ShareBars
              format={fmtMinutes}
              rows={s.time.distribution.map((r) => {
                const cat = r.category_id ? byId.get(r.category_id) : undefined;
                return {
                  key: r.category_id ?? 'none',
                  label: cat ? label(cat) : t('distribution.none'),
                  color: r.color ?? '#94a3b8',
                  value: r.minutes,
                  share: r.share ?? 0,
                };
              })}
            />
          ) : (
            <p className={styles.muted}>{t('distribution.empty')}</p>
          )}
          <p className={styles.subtle}>
            {t('pva', {
              planned: fmtMinutes(s.time.planned_minutes),
              actual: fmtMinutes(s.time.actual_minutes),
              unplanned: fmtMinutes(s.time.unplanned_minutes),
            })}
          </p>
        </section>
        <aside className={styles.panel} aria-labelledby="tasks-title">
          <h3 id="tasks-title">{t('tasksBlock.title')}</h3>
          <dl className={styles.stats}>
            <div className={styles.stat}>
              <dt>{t('tasksBlock.completed')}</dt>
              <dd>{s.tasks.completed}</dd>
            </div>
            <div className={styles.stat}>
              <dt>{t('tasksBlock.overdue')}</dt>
              <dd>{s.tasks.overdue_open}</dd>
            </div>
            <div className={styles.stat}>
              <dt>{t('tasksBlock.postponed')}</dt>
              <dd>{s.tasks.postponed}</dd>
            </div>
            <div className={styles.stat}>
              <dt>{t('tasksBlock.created')}</dt>
              <dd>{s.tasks.created}</dd>
            </div>
          </dl>
        </aside>
      </div>

      <div className={styles.split}>
        <section className={styles.panel} aria-labelledby="habits-title">
          <h3 id="habits-title">{t('habitsBlock.title')}</h3>
          {s.habits.habits.length ? (
            <ShareBars
              showShare={false}
              format={(v) => `${Math.round(v * 100)}%`}
              rows={s.habits.habits.map((h) => ({
                key: h.id,
                label: h.name,
                color: h.color ?? 'var(--color-primary)',
                value: h.consistency ?? 0,
                share: h.consistency ?? 0,
              }))}
            />
          ) : (
            <p className={styles.muted}>{t('habitsBlock.empty')}</p>
          )}
        </section>
        <aside className={styles.panel} aria-labelledby="goals-title">
          <h3 id="goals-title">{t('goalsBlock.title')}</h3>
          {s.goals.active.length ? (
            <ul className={styles.list}>
              {s.goals.active.map((g) => (
                <li key={g.id}>
                  <Link to={`/goals/${g.id}`} className={a.goal}>
                    <span>{g.title}</span>
                    <b>{Math.round(g.progress_pct)}%</b>
                    <i className={styles.bar} aria-hidden="true">
                      <i style={{ width: `${g.progress_pct}%` }} />
                    </i>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>{t('goalsBlock.empty')}</p>
          )}
          <p className={styles.subtle}>
            {t('goalsBlock.completed', { count: s.goals.completed_in_period })}
          </p>
        </aside>
      </div>

      {s.wellness.checkins || s.wellness.sleep_entries ? (
        <section className={styles.panel} aria-labelledby="well-title">
          <h3 id="well-title">{t('wellnessBlock.title')}</h3>
          <dl className={styles.stats}>
            <div className={styles.stat}>
              <dt>{t('wellnessBlock.mood')}</dt>
              <dd>{s.wellness.mood === null ? '—' : s.wellness.mood.toFixed(1)}</dd>
            </div>
            <div className={styles.stat}>
              <dt>{t('wellnessBlock.energy')}</dt>
              <dd>{s.wellness.energy === null ? '—' : s.wellness.energy.toFixed(1)}</dd>
            </div>
            <div className={styles.stat}>
              <dt>{t('wellnessBlock.stress')}</dt>
              <dd>{s.wellness.stress === null ? '—' : s.wellness.stress.toFixed(1)}</dd>
            </div>
            <div className={styles.stat}>
              <dt>{t('wellnessBlock.sleep')}</dt>
              <dd>
                {s.wellness.sleep_minutes ? fmtMinutes(Math.round(s.wellness.sleep_minutes)) : '—'}
              </dd>
            </div>
          </dl>
        </section>
      ) : null}
      <p className={styles.subtle}>{t('footer', { version: s.formula_version })}</p>
    </>
  );
}
