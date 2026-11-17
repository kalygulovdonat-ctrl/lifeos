import { useMutation } from '@tanstack/react-query';
import { AlertTriangle, Check, CircleSlash, Trash2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useCategories, useInvalidatePlanning } from '@/modules/planning/hooks';
import { TIME_TYPE_META } from '@/modules/planning/meta';
import { ApiError } from '@/shared/api/client';
import { scheduleApi, type EventInput } from '@/shared/api/planning';
import {
  TIME_TYPES,
  type CalendarEvent,
  type EventBrief,
  type Recurrence,
  type TimeType,
  type Weekday,
} from '@/shared/api/types';
import { Modal, Notice, TextArea } from '@/shared/components/overlay';
import { Alert, Button, SelectField, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { usePrefs } from '@/shared/hooks/usePrefs';
import { clockOf, clockOptions, dateKey, isoWeekday, zonedIso } from '@/shared/utils/datetime';

import styles from './schedule.module.css';

export type EditorTarget =
  | { mode: 'create'; date: string; start: string; end?: string; timeType?: TimeType }
  | { mode: 'edit'; event: CalendarEvent };

type Repeat = 'none' | 'daily' | 'weekdays' | 'weekly' | 'monthly';
type Scope = 'this' | 'following' | 'all';
const WEEKDAYS: Weekday[] = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'];

function repeatOf(r: Recurrence | null): Repeat {
  if (!r) return 'none';
  if (r.freq === 'DAILY') return 'daily';
  if (r.freq === 'MONTHLY') return 'monthly';
  if (r.freq === 'WEEKLY' && r.by_day?.length === 5 && !r.by_day.includes('SA')) return 'weekdays';
  return 'weekly';
}

function recurrenceOf(repeat: Repeat, date: string, until: string): Recurrence | null {
  const end = until || null;
  switch (repeat) {
    case 'daily':
      return { freq: 'DAILY', until: end };
    case 'weekdays':
      return { freq: 'WEEKLY', by_day: ['MO', 'TU', 'WE', 'TH', 'FR'], until: end };
    case 'weekly':
      return { freq: 'WEEKLY', by_day: [WEEKDAYS[isoWeekday(date) - 1]!], until: end };
    case 'monthly':
      return { freq: 'MONTHLY', by_month_day: [Number(date.slice(8))], until: end };
    default:
      return null;
  }
}

const plusHour = (hhmm: string) => {
  const [h = 0, m = 0] = hhmm.split(':').map(Number);
  const total = Math.min(h * 60 + m + 60, 23 * 60 + 30);
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};

export function EventEditor({
  target,
  onClose,
}: {
  target: EditorTarget | null;
  onClose: () => void;
}) {
  const { t } = useTranslation('schedule');
  const open = target !== null;
  const title = target?.mode === 'edit' ? t('editor.editTitle') : t('editor.createTitle');
  return (
    <Modal open={open} onClose={onClose} title={title} size="md">
      {target ? (
        <EditorBody key={JSON.stringify(target)} target={target} onClose={onClose} />
      ) : null}
    </Modal>
  );
}

function EditorBody({ target, onClose }: { target: EditorTarget; onClose: () => void }) {
  const { t } = useTranslation('schedule');
  const errorMessage = useErrorMessage();
  const invalidate = useInvalidatePlanning();
  const prefs = usePrefs();
  const { categories, label } = useCategories();
  const editing = target.mode === 'edit' ? target.event : null;
  const recurring = Boolean(editing?.series_id);

  const [form, setForm] = useState(() => {
    if (editing) {
      const s = new Date(editing.start_at);
      return {
        title: editing.title,
        timeType: editing.time_type,
        date: dateKey(s, prefs.timezone),
        start: clockOf(s, prefs.timezone),
        end: clockOf(new Date(editing.end_at), prefs.timezone),
        repeat: repeatOf(editing.recurrence),
        until: editing.recurrence?.until ?? '',
        categoryId: editing.category_id ?? '',
        location: editing.location,
        description: editing.description,
        reminder: editing.reminder_minutes === null ? '' : String(editing.reminder_minutes),
      };
    }
    const c = target as Extract<EditorTarget, { mode: 'create' }>;
    return {
      title: '',
      timeType: c.timeType ?? ('PERSONAL' as TimeType),
      date: c.date,
      start: c.start,
      end: c.end ?? plusHour(c.start),
      repeat: 'none' as Repeat,
      until: '',
      categoryId: '',
      location: '',
      description: '',
      reminder: '',
    };
  });
  const [scope, setScope] = useState<Scope>('this');
  const [hardConflict, setHardConflict] = useState<EventBrief[] | null>(null);
  const [preview, setPreview] = useState<Array<{ severity: string; event: EventBrief }>>([]);

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setHardConflict(null);
  };

  const startIso = zonedIso(form.date, form.start, prefs.timezone);
  const endIso = zonedIso(form.date, form.end, prefs.timezone);
  const validRange = form.end > form.start;

  // Live conflict preview (SCH-011): warns before saving, the server still decides.
  useEffect(() => {
    if (!validRange || !form.date) return;
    const handle = window.setTimeout(() => {
      scheduleApi
        .checkConflicts({
          start_at: startIso,
          end_at: endIso,
          time_type: form.timeType,
          exclude_id: editing?.id ?? null,
        })
        .then((r) =>
          setPreview(
            r.results.filter(
              (x) => !editing?.occurrence_key || x.event.occurrence_key !== editing.occurrence_key,
            ),
          ),
        )
        .catch(() => setPreview([]));
    }, 350);
    return () => window.clearTimeout(handle);
  }, [
    startIso,
    endIso,
    form.timeType,
    form.date,
    validRange,
    editing?.id,
    editing?.occurrence_key,
  ]);

  const payload = (): EventInput => ({
    title: form.title.trim(),
    time_type: form.timeType,
    start_at: startIso,
    end_at: endIso,
    category_id: form.categoryId || null,
    location: form.location,
    description: form.description,
    reminder_minutes: form.reminder === '' ? null : Number(form.reminder),
  });

  const save = useMutation({
    mutationFn: async (force: boolean) => {
      const data = payload();
      const recurrence = recurrenceOf(form.repeat, form.date, form.until);
      if (!editing) return scheduleApi.create({ ...data, recurrence }, force);
      if (!recurring) return scheduleApi.update(editing.id!, data, force);
      if (scope === 'all') {
        const series = await scheduleApi.getSeries(editing.series_id!);
        const day = dateKey(new Date(series.start_at), prefs.timezone);
        return scheduleApi.updateSeries(
          editing.series_id!,
          {
            ...data,
            start_at: zonedIso(day, form.start, prefs.timezone),
            end_at: zonedIso(day, form.end, prefs.timezone),
            recurrence: recurrence ?? undefined,
          },
          force,
        );
      }
      if (scope === 'following')
        return scheduleApi.updateOccurrence(
          editing,
          { ...data, scope: 'following', recurrence },
          force,
        );
      return scheduleApi.updateOccurrence(editing, data, force);
    },
    onSuccess: onClose,
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'SCHEDULE_CONFLICT') {
        setHardConflict((err.details.conflicting as EventBrief[] | undefined) ?? []);
      }
    },
    onSettled: invalidate,
  });

  const action = useMutation({
    mutationFn: async (kind: 'DONE' | 'MISSED' | 'CANCELLED' | 'delete' | 'deleteSeries') => {
      if (!editing) return;
      if (kind === 'deleteSeries') return scheduleApi.removeSeries(editing.series_id!);
      if (kind === 'delete')
        return editing.series_id
          ? scheduleApi.cancelOccurrence(editing)
          : scheduleApi.remove(editing.id!);
      if (editing.id) return scheduleApi.setStatus(editing.id, kind);
      return scheduleApi.updateOccurrence(editing, { status: kind });
    },
    onSuccess: onClose,
    onSettled: invalidate,
  });

  const fieldErrors = save.error instanceof ApiError ? save.error.fieldErrors() : {};
  const options = clockOptions(prefs.timeFormat, form.start);
  const showRepeat = !editing || !recurring || scope !== 'this';
  const warnings = preview.filter((p) => p.severity === 'WARNING' || p.severity === 'CONFLICT');

  return (
    <>
      <TextField
        label={t('editor.title')}
        value={form.title}
        onChange={(e) => set('title', e.target.value)}
        placeholder={t('editor.titlePlaceholder')}
        error={fieldErrors.title}
        maxLength={200}
        data-autofocus
      />

      <div role="radiogroup" aria-label={t('editor.type')} className={styles.types}>
        {TIME_TYPES.map((type) => {
          const meta = TIME_TYPE_META[type];
          const Icon = meta.icon;
          return (
            <button
              type="button"
              role="radio"
              aria-checked={form.timeType === type}
              key={type}
              className={styles.typeChip}
              style={{ ['--c' as string]: meta.color }}
              onClick={() => set('timeType', type)}
            >
              <Icon size={14} />
              {t(`timeType.${type}`)}
            </button>
          );
        })}
      </div>
      <p className={styles.typeHint}>{t(`timeTypeHint.${form.timeType}`)}</p>

      <div className={styles.formRow}>
        <TextField
          label={t('editor.date')}
          type="date"
          value={form.date}
          onChange={(e) => set('date', e.target.value)}
        />
        <SelectField
          label={t('editor.start')}
          value={form.start}
          options={options}
          onChange={(e) => {
            const start = e.target.value;
            setForm((f) => ({ ...f, start, end: f.end > start ? f.end : plusHour(start) }));
          }}
        />
        <SelectField
          label={t('editor.end')}
          value={form.end}
          options={clockOptions(prefs.timeFormat, form.end)}
          onChange={(e) => set('end', e.target.value)}
          error={!validRange ? t('editor.endBeforeStart') : fieldErrors.end_at}
        />
      </div>

      {recurring ? (
        <div role="radiogroup" aria-label={t('editor.scope')} className={styles.scope}>
          <span>{t('editor.scope')}</span>
          {(['this', 'following', 'all'] as Scope[]).map((s) => (
            <label key={s}>
              <input type="radio" name="scope" checked={scope === s} onChange={() => setScope(s)} />
              {t(`editor.scopes.${s}`)}
            </label>
          ))}
        </div>
      ) : null}

      {showRepeat ? (
        <div className={styles.formRow}>
          <SelectField
            label={t('editor.repeat')}
            value={form.repeat}
            onChange={(e) => set('repeat', e.target.value as Repeat)}
            options={(['none', 'daily', 'weekdays', 'weekly', 'monthly'] as Repeat[]).map((r) => ({
              value: r,
              label: t(`repeat.${r}`),
            }))}
          />
          {form.repeat !== 'none' ? (
            <TextField
              label={t('editor.until')}
              type="date"
              value={form.until}
              min={form.date}
              onChange={(e) => set('until', e.target.value)}
            />
          ) : null}
        </div>
      ) : null}

      <div className={styles.formRow}>
        <SelectField
          label={t('editor.category')}
          value={form.categoryId}
          onChange={(e) => set('categoryId', e.target.value)}
          options={[
            { value: '', label: t('editor.noCategory') },
            ...categories.map((c) => ({ value: c.id, label: label(c) })),
          ]}
        />
        <SelectField
          label={t('editor.reminder')}
          value={form.reminder}
          onChange={(e) => set('reminder', e.target.value)}
          options={[
            { value: '', label: t('editor.noReminder') },
            ...[0, 5, 10, 15, 30, 60].map((m) => ({
              value: String(m),
              label: m === 0 ? t('editor.atStart') : t('editor.reminderBefore', { count: m }),
            })),
          ]}
        />
      </div>
      <TextField
        label={t('editor.location')}
        value={form.location}
        onChange={(e) => set('location', e.target.value)}
        maxLength={200}
      />
      <TextArea
        label={t('editor.description')}
        value={form.description}
        onChange={(e) => set('description', e.target.value)}
        rows={2}
      />

      {editing?.task ? (
        <Notice tone="info">{t('editor.linkedTask', { title: editing.task.title ?? '' })}</Notice>
      ) : null}

      {hardConflict ? (
        <Notice tone="danger" icon={<AlertTriangle size={16} />}>
          <strong>{t('editor.conflictTitle')}</strong> {hardConflict.map((c) => c.title).join(', ')}
          . {t('editor.conflictHint')}
        </Notice>
      ) : warnings.length ? (
        <Notice
          tone={warnings.some((w) => w.severity === 'CONFLICT') ? 'danger' : 'warning'}
          icon={<AlertTriangle size={16} />}
        >
          <strong>{t('editor.overlapTitle')}</strong>{' '}
          {warnings.map((w) => w.event.title).join(', ')}
        </Notice>
      ) : null}
      {save.error && !hardConflict ? <Alert>{errorMessage(save.error)}</Alert> : null}
      {action.error ? <Alert>{errorMessage(action.error)}</Alert> : null}

      <div className={styles.editorFoot}>
        {editing ? (
          <div className={styles.editorActions}>
            {editing.status !== 'DONE' ? (
              <Button
                variant="secondary"
                size="sm"
                icon={<Check size={15} />}
                onClick={() => action.mutate('DONE')}
              >
                {t('editor.markDone')}
              </Button>
            ) : null}
            {editing.status === 'PLANNED' ? (
              <Button
                variant="ghost"
                size="sm"
                icon={<X size={15} />}
                onClick={() => action.mutate('MISSED')}
              >
                {t('editor.markMissed')}
              </Button>
            ) : null}
            {editing.status !== 'CANCELLED' ? (
              <Button
                variant="ghost"
                size="sm"
                icon={<CircleSlash size={15} />}
                onClick={() => action.mutate('CANCELLED')}
              >
                {t('editor.markCancelled')}
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              icon={<Trash2 size={15} />}
              onClick={() => action.mutate('delete')}
            >
              {recurring ? t('editor.deleteOne') : t('editor.delete')}
            </Button>
            {recurring ? (
              <Button
                variant="ghost"
                size="sm"
                icon={<Trash2 size={15} />}
                onClick={() => action.mutate('deleteSeries')}
              >
                {t('editor.deleteSeries')}
              </Button>
            ) : null}
          </div>
        ) : (
          <span />
        )}
        <div className={styles.editorActions}>
          <Button variant="ghost" onClick={onClose}>
            {t('editor.close')}
          </Button>
          {hardConflict ? (
            <Button loading={save.isPending} onClick={() => save.mutate(true)}>
              {t('editor.saveAnyway')}
            </Button>
          ) : (
            <Button
              loading={save.isPending}
              disabled={!form.title.trim() || !validRange}
              onClick={() => save.mutate(false)}
            >
              {t('editor.save')}
            </Button>
          )}
        </div>
      </div>
    </>
  );
}
