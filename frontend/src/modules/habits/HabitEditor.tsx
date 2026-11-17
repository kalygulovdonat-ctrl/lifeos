import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import styles from '@/modules/growth.module.css';
import { useCategories, useInvalidatePlanning } from '@/modules/planning/hooks';
import { ApiError } from '@/shared/api/client';
import { habitsApi, type HabitInput } from '@/shared/api/growth';
import type { FrequencyType, HabitDetail, TrackingType } from '@/shared/api/types';
import { Modal } from '@/shared/components/overlay';
import { Alert, Button, SelectField, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { useToday } from '@/shared/hooks/usePrefs';

const TYPES: TrackingType[] = ['BOOLEAN', 'QUANTITY', 'DURATION', 'SCALE'];
const FREQS: FrequencyType[] = [
  'DAILY',
  'WEEKDAYS',
  'TIMES_PER_WEEK',
  'TIMES_PER_MONTH',
  'EVERY_N_DAYS',
];
const WEEKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'] as const;
const HABIT_COLORS = [
  '#8B5CF6',
  '#3B82F6',
  '#10B981',
  '#F97316',
  '#EC4899',
  '#EAB308',
  '#14B8A6',
  '#EF4444',
];

export function HabitEditor({
  open,
  onClose,
  habit,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  habit?: HabitDetail;
  onSaved?: (h: HabitDetail) => void;
}) {
  const { t } = useTranslation('habits');
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={habit ? t('editor.editTitle') : t('editor.createTitle')}
    >
      {open ? <Body habit={habit} onClose={onClose} onSaved={onSaved} /> : null}
    </Modal>
  );
}

function Body({
  habit,
  onClose,
  onSaved,
}: {
  habit?: HabitDetail;
  onClose: () => void;
  onSaved?: (h: HabitDetail) => void;
}) {
  const { t } = useTranslation('habits');
  const errorMessage = useErrorMessage();
  const invalidate = useInvalidatePlanning();
  const today = useToday();
  const { categories, label } = useCategories();
  const s = habit?.schedule;
  const [f, setF] = useState({
    name: habit?.name ?? '',
    type: habit?.tracking_type ?? ('BOOLEAN' as TrackingType),
    unit: habit?.unit ?? '',
    scaleMin: String(habit?.scale_min ?? 1),
    scaleMax: String(habit?.scale_max ?? 5),
    freq: s?.frequency_type ?? ('DAILY' as FrequencyType),
    mask: s?.weekdays_mask ?? 0b0011111,
    times: String(s?.times_per_period ?? 3),
    interval: String(s?.interval_days ?? 2),
    target: s?.target_value ? String(Number(s.target_value)) : '',
    comparison: s?.target_comparison ?? ('GTE' as 'GTE' | 'LTE'),
    start: habit?.start_date ?? today,
    categoryId: habit?.category_id ?? '',
    color: habit?.color ?? HABIT_COLORS[0]!,
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const save = useMutation({
    mutationFn: () => {
      const input: HabitInput = {
        name: f.name.trim(),
        tracking_type: f.type,
        unit: f.type === 'QUANTITY' ? f.unit.trim() : undefined,
        scale_min: f.type === 'SCALE' ? Number(f.scaleMin) : null,
        scale_max: f.type === 'SCALE' ? Number(f.scaleMax) : null,
        start_date: f.start,
        category_id: f.categoryId || null,
        color: f.color,
        schedule: {
          frequency_type: f.freq,
          weekdays_mask: f.freq === 'WEEKDAYS' ? f.mask : null,
          times_per_period: f.freq.startsWith('TIMES') ? Number(f.times) : null,
          interval_days: f.freq === 'EVERY_N_DAYS' ? Number(f.interval) : null,
          target_value: f.type === 'BOOLEAN' || !f.target ? null : f.target,
          target_comparison: f.comparison,
        },
      };
      return habit ? habitsApi.update(habit.id, input) : habitsApi.create(input);
    },
    onSuccess: (h) => {
      onSaved?.(h);
      onClose();
    },
    onSettled: invalidate,
  });
  const errors = save.error instanceof ApiError ? save.error.fieldErrors() : {};
  const needsTarget = f.type === 'QUANTITY' || f.type === 'DURATION';

  return (
    <>
      <TextField
        label={t('editor.name')}
        value={f.name}
        onChange={(e) => set('name', e.target.value)}
        placeholder={t('editor.namePlaceholder')}
        error={errors.name}
        maxLength={120}
        data-autofocus
      />
      <div>
        <p className={styles.subtle}>{t('editor.type')}</p>
        <div className={styles.pills} role="radiogroup" aria-label={t('editor.type')}>
          {TYPES.map((type) => (
            <button
              key={type}
              type="button"
              role="radio"
              aria-checked={f.type === type}
              onClick={() => set('type', type)}
            >
              {t(`type.${type}`)}
            </button>
          ))}
        </div>
        <p className={styles.subtle}>{t(`typeHint.${f.type}`)}</p>
      </div>
      {f.type === 'QUANTITY' ? (
        <TextField
          label={t('editor.unit')}
          value={f.unit}
          onChange={(e) => set('unit', e.target.value)}
          placeholder={t('editor.unitPlaceholder')}
          maxLength={20}
        />
      ) : null}
      {f.type === 'SCALE' ? (
        <div className={styles.formGrid}>
          <TextField
            label={t('editor.scaleMin')}
            type="number"
            value={f.scaleMin}
            onChange={(e) => set('scaleMin', e.target.value)}
          />
          <TextField
            label={t('editor.scaleMax')}
            type="number"
            value={f.scaleMax}
            onChange={(e) => set('scaleMax', e.target.value)}
            error={errors.scale_max}
          />
        </div>
      ) : null}

      <div>
        <p className={styles.subtle}>{t('editor.frequency')}</p>
        <div className={styles.pills} role="radiogroup" aria-label={t('editor.frequency')}>
          {FREQS.map((freq) => (
            <button
              key={freq}
              type="button"
              role="radio"
              aria-checked={f.freq === freq}
              onClick={() => set('freq', freq)}
            >
              {t(`freq.${freq}`)}
            </button>
          ))}
        </div>
      </div>
      {f.freq === 'WEEKDAYS' ? (
        <div className={styles.pills} role="group" aria-label={t('editor.weekdays')}>
          {WEEKDAYS.map((d, i) => (
            <button
              key={d}
              type="button"
              aria-pressed={Boolean(f.mask & (1 << i))}
              onClick={() => set('mask', f.mask ^ (1 << i))}
            >
              {t(`weekday.${d}`)}
            </button>
          ))}
        </div>
      ) : null}
      {f.freq === 'TIMES_PER_WEEK' || f.freq === 'TIMES_PER_MONTH' ? (
        <TextField
          label={t('editor.times')}
          type="number"
          min={1}
          value={f.times}
          onChange={(e) => set('times', e.target.value)}
          error={errors.times_per_period}
        />
      ) : null}
      {f.freq === 'EVERY_N_DAYS' ? (
        <TextField
          label={t('editor.interval')}
          type="number"
          min={2}
          value={f.interval}
          onChange={(e) => set('interval', e.target.value)}
          error={errors.interval_days}
        />
      ) : null}

      {f.type !== 'BOOLEAN' ? (
        <div className={styles.formGrid}>
          <TextField
            label={
              needsTarget
                ? t('editor.target', { unit: f.type === 'DURATION' ? t('min') : f.unit })
                : t('editor.scaleTarget')
            }
            type="number"
            min={0}
            step="any"
            value={f.target}
            onChange={(e) => set('target', e.target.value)}
            error={errors.target_value}
          />
          <SelectField
            label={t('editor.comparison')}
            value={f.comparison}
            onChange={(e) => set('comparison', e.target.value as 'GTE' | 'LTE')}
            options={[
              { value: 'GTE', label: t('comparison.GTE') },
              { value: 'LTE', label: t('comparison.LTE') },
            ]}
          />
        </div>
      ) : null}

      <div className={styles.formGrid}>
        <TextField
          label={t('editor.start')}
          type="date"
          value={f.start}
          onChange={(e) => set('start', e.target.value)}
        />
        <SelectField
          label={t('editor.category')}
          value={f.categoryId}
          onChange={(e) => set('categoryId', e.target.value)}
          options={[
            { value: '', label: t('editor.noCategory') },
            ...categories.map((c) => ({ value: c.id, label: label(c) })),
          ]}
        />
      </div>
      <div className={styles.pills} role="radiogroup" aria-label={t('editor.color')}>
        {HABIT_COLORS.map((c) => (
          <button
            key={c}
            type="button"
            role="radio"
            aria-checked={f.color === c}
            aria-label={c}
            onClick={() => set('color', c)}
            style={{
              width: 32,
              padding: 0,
              background: c,
              borderColor: f.color === c ? 'var(--color-text)' : 'transparent',
            }}
          />
        ))}
      </div>
      {habit ? <p className={styles.subtle}>{t('editor.versionHint')}</p> : null}
      {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
      <div className={styles.row} style={{ justifyContent: 'flex-end' }}>
        <Button variant="ghost" onClick={onClose}>
          {t('editor.cancel')}
        </Button>
        <Button
          loading={save.isPending}
          disabled={!f.name.trim() || (needsTarget && !f.target)}
          onClick={() => save.mutate()}
        >
          {t('editor.save')}
        </Button>
      </div>
    </>
  );
}
