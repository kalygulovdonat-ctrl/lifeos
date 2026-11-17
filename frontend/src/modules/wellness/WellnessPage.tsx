import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { HeartPulse, Moon, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import styles from '@/modules/growth.module.css';
import { useMinutesLabel } from '@/modules/time/useTimer';
import { insightKeys, wellnessApi } from '@/shared/api/insight';
import { ColumnChart, LineChart } from '@/shared/components/charts';
import { Notice } from '@/shared/components/overlay';
import { Alert, Button, PageHeader, SelectField, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs, useToday } from '@/shared/hooks/usePrefs';
import { addDays, clockOptions, formatKey, formatTime, zonedIso } from '@/shared/utils/datetime';

import w from './wellness.module.css';

const SCALE = Array.from({ length: 10 }, (_, i) => i + 1);
type Field = 'mood' | 'energy' | 'stress';

function ScalePicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  return (
    <div>
      <p className={styles.subtle}>{label}</p>
      <div className={w.scale} role="radiogroup" aria-label={label}>
        {SCALE.map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            onClick={() => onChange(value === n ? null : n)}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function WellnessPage() {
  const { t } = useTranslation('wellness');
  const prefs = usePrefs();
  const today = useToday();
  const fmtMinutes = useMinutesLabel();
  const from = addDays(today, -29);
  const summary = useQuery({
    queryKey: insightKeys.wellnessSummary(from, today),
    queryFn: () => wellnessApi.summary(from, today),
  });
  const checkins = useQuery({
    queryKey: insightKeys.checkins(addDays(today, -6), today),
    queryFn: () => wellnessApi.checkins(addDays(today, -6), today),
  });
  const sleeps = useQuery({
    queryKey: insightKeys.sleeps(addDays(today, -6), today),
    queryFn: () => wellnessApi.sleeps(addDays(today, -6), today),
  });
  const qc = useQueryClient();
  const refresh = () => void qc.invalidateQueries({ queryKey: insightKeys.wellness });
  const removeCheckin = useMutation({ mutationFn: wellnessApi.removeCheckin, onSettled: refresh });
  const removeSleep = useMutation({ mutationFn: wellnessApi.removeSleep, onSettled: refresh });
  const s = summary.data;
  const series = s?.series ?? [];
  const short = (d: string) => formatKey(d, prefs.language, { day: 'numeric', month: 'short' });
  const long = (d: string) =>
    formatKey(d, prefs.language, { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className={styles.page}>
      <PageHeader title={t('title')} description={t('subtitle')} />
      {s?.signals?.length ? (
        <Notice tone="warning" icon={<HeartPulse size={16} />}>
          <strong>{t('signals.title')}</strong>
          <ul className={w.signals}>
            {s.signals.map((sig) => (
              <li key={sig.code}>{t(`signals.${sig.code}`, sig as Record<string, unknown>)}</li>
            ))}
          </ul>
          <span>{t('signals.disclaimer')}</span>
        </Notice>
      ) : null}

      <div className={styles.split}>
        <CheckinForm onSaved={refresh} />
        <SleepForm onSaved={refresh} />
      </div>

      {s ? (
        <dl className={styles.stats}>
          {(['mood', 'energy', 'stress'] as Field[]).map((f) => (
            <div className={styles.stat} key={f}>
              <dt>
                {t(`fields.${f}`)} · 30 {t('days')}
              </dt>
              <dd>{s[f] === null ? '—' : s[f].toFixed(1)}</dd>
            </div>
          ))}
          <div className={styles.stat}>
            <dt>
              {t('fields.sleep')} · 30 {t('days')}
            </dt>
            <dd>{s.sleep_minutes ? fmtMinutes(Math.round(s.sleep_minutes)) : '—'}</dd>
          </div>
        </dl>
      ) : null}

      {series.some((d) => d.mood !== null || d.energy !== null || d.stress !== null) ? (
        <section className={styles.panel} aria-labelledby="trend-title">
          <h3 id="trend-title">{t('charts.state')}</h3>
          <LineChart
            ariaLabel={t('charts.state')}
            labels={series.map((d) => short(d.date))}
            titles={series.map((d) => long(d.date))}
            min={1}
            max={10}
            format={(v) => (Number.isInteger(v) ? String(v) : v.toFixed(1))}
            series={(['mood', 'energy', 'stress'] as Field[]).map((f) => ({
              key: f,
              label: t(`fields.${f}`),
              values: series.map((d) => d[f]),
            }))}
          />
        </section>
      ) : null}

      {series.some((d) => d.sleep_minutes) ? (
        <section className={styles.panel} aria-labelledby="sleep-title">
          <h3 id="sleep-title">{t('charts.sleep')}</h3>
          <ColumnChart
            ariaLabel={t('charts.sleep')}
            tableLabel={t('charts.sleep')}
            format={(v) => t('hours', { value: v.toFixed(1) })}
            data={series.map((d) => ({
              key: d.date,
              label: short(d.date),
              title: long(d.date),
              value: (d.sleep_minutes ?? 0) / 60,
            }))}
          />
        </section>
      ) : null}

      <div className={styles.split}>
        <section className={styles.panel} aria-labelledby="recent-title">
          <h3 id="recent-title">{t('recent.checkins')}</h3>
          {checkins.data?.length ? (
            <ul className={styles.list}>
              {checkins.data.map((c) => (
                <li key={c.id} className={styles.item}>
                  <div className={styles.itemLink}>
                    <strong>
                      {short(c.local_date)}, {formatTime(new Date(c.recorded_at), prefs)}
                    </strong>
                    <small>
                      {(['mood', 'energy', 'stress'] as Field[])
                        .filter((f) => c[f] !== null)
                        .map((f) => `${t(`fields.${f}`)} ${c[f]}`)
                        .join(' · ')}
                      {c.source === 'JOURNAL' ? ` · ${t('fromJournal')}` : ''}
                    </small>
                  </div>
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={() => removeCheckin.mutate(c.id)}
                    aria-label={t('delete')}
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>{t('recent.none')}</p>
          )}
        </section>
        <aside className={styles.panel} aria-labelledby="recent-sleep">
          <h3 id="recent-sleep">{t('recent.sleep')}</h3>
          {sleeps.data?.length ? (
            <ul className={styles.list}>
              {sleeps.data.map((x) => (
                <li key={x.id} className={styles.item}>
                  <div className={styles.itemLink}>
                    <strong>{fmtMinutes(x.minutes)}</strong>
                    <small>
                      {short(x.wake_date)} · {formatTime(new Date(x.sleep_start), prefs)}–
                      {formatTime(new Date(x.sleep_end), prefs)}
                      {x.quality ? ` · ${t('fields.quality')} ${x.quality}` : ''}
                    </small>
                  </div>
                  <button
                    type="button"
                    className={styles.iconBtn}
                    onClick={() => removeSleep.mutate(x.id)}
                    aria-label={t('delete')}
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.muted}>{t('recent.none')}</p>
          )}
        </aside>
      </div>
      <p className={styles.subtle}>{t('disclaimer')}</p>
    </div>
  );
}

function CheckinForm({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation('wellness');
  const errorMessage = useErrorMessage();
  const [v, setV] = useState<Record<Field, number | null>>({
    mood: null,
    energy: null,
    stress: null,
  });
  const [note, setNote] = useState('');
  const save = useMutation({
    mutationFn: () => wellnessApi.addCheckin({ ...v, note }),
    onSuccess: () => {
      setV({ mood: null, energy: null, stress: null });
      setNote('');
      onSaved();
    },
  });
  return (
    <section className={styles.panel} aria-labelledby="checkin-title">
      <h2 id="checkin-title">
        <HeartPulse size={16} /> {t('checkin.title')}
      </h2>
      {(['mood', 'energy', 'stress'] as Field[]).map((f) => (
        <ScalePicker
          key={f}
          label={t(`checkin.${f}`)}
          value={v[f]}
          onChange={(n) => setV((x) => ({ ...x, [f]: n }))}
        />
      ))}
      <TextField
        label={t('checkin.note')}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={500}
      />
      <Button
        loading={save.isPending}
        disabled={v.mood === null && v.energy === null && v.stress === null}
        onClick={() => save.mutate()}
      >
        {t('checkin.save')}
      </Button>
      {save.isSuccess ? <p className={styles.subtle}>{t('saved')}</p> : null}
      {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
    </section>
  );
}

function SleepForm({ onSaved }: { onSaved: () => void }) {
  const { t } = useTranslation('wellness');
  const prefs = usePrefs();
  const today = useToday();
  const errorMessage = useErrorMessage();
  const [bed, setBed] = useState({ date: addDays(today, -1), time: '23:30' });
  const [wake, setWake] = useState({ date: today, time: '07:30' });
  const [quality, setQuality] = useState<number | null>(null);
  const save = useMutation({
    mutationFn: () =>
      wellnessApi.addSleep({
        sleep_start: zonedIso(bed.date, bed.time, prefs.timezone),
        sleep_end: zonedIso(wake.date, wake.time, prefs.timezone),
        quality,
      }),
    onSuccess: () => {
      setQuality(null);
      onSaved();
    },
  });
  return (
    <aside className={styles.panel} aria-labelledby="sleep-form-title">
      <h2 id="sleep-form-title">
        <Moon size={16} /> {t('sleep.title')}
      </h2>
      <div className={styles.formGrid}>
        <TextField
          label={t('sleep.bedDate')}
          type="date"
          value={bed.date}
          max={today}
          onChange={(e) => setBed((b) => ({ ...b, date: e.target.value }))}
        />
        <SelectField
          label={t('sleep.bedTime')}
          value={bed.time}
          options={clockOptions(prefs.timeFormat, bed.time)}
          onChange={(e) => setBed((b) => ({ ...b, time: e.target.value }))}
        />
        <TextField
          label={t('sleep.wakeDate')}
          type="date"
          value={wake.date}
          max={today}
          onChange={(e) => setWake((b) => ({ ...b, date: e.target.value }))}
        />
        <SelectField
          label={t('sleep.wakeTime')}
          value={wake.time}
          options={clockOptions(prefs.timeFormat, wake.time)}
          onChange={(e) => setWake((b) => ({ ...b, time: e.target.value }))}
        />
      </div>
      <ScalePicker label={t('sleep.quality')} value={quality} onChange={setQuality} />
      <Button variant="secondary" loading={save.isPending} onClick={() => save.mutate()}>
        {t('sleep.save')}
      </Button>
      {save.isSuccess ? <p className={styles.subtle}>{t('saved')}</p> : null}
      {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
    </aside>
  );
}
