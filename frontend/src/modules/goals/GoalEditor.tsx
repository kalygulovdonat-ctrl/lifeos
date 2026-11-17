import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import styles from '@/modules/growth.module.css';
import { useCategories, useInvalidatePlanning } from '@/modules/planning/hooks';
import { ApiError } from '@/shared/api/client';
import { goalsApi, growthKeys, type GoalInput } from '@/shared/api/growth';
import type { GoalDetail, GoalLevel, ProgressType } from '@/shared/api/types';
import { Modal, TextArea } from '@/shared/components/overlay';
import { Alert, Button, SelectField, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { useToday } from '@/shared/hooks/usePrefs';

const LEVELS: GoalLevel[] = ['VISION', 'YEARLY', 'QUARTERLY', 'MONTHLY', 'CUSTOM'];
const TYPES: ProgressType[] = ['MILESTONES', 'TASKS', 'METRIC', 'MANUAL'];

export function GoalEditor({
  open,
  onClose,
  goal,
  parentId,
}: {
  open: boolean;
  onClose: () => void;
  goal?: GoalDetail;
  parentId?: string;
}) {
  const { t } = useTranslation('goals');
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={goal ? t('editor.editTitle') : t('editor.createTitle')}
    >
      {open ? <Body goal={goal} parentId={parentId} onClose={onClose} /> : null}
    </Modal>
  );
}

function Body({
  goal,
  parentId,
  onClose,
}: {
  goal?: GoalDetail;
  parentId?: string;
  onClose: () => void;
}) {
  const { t } = useTranslation('goals');
  const navigate = useNavigate();
  const errorMessage = useErrorMessage();
  const invalidate = useInvalidatePlanning();
  const today = useToday();
  const { categories, label } = useCategories();
  const all = useQuery({ queryKey: [...growthKeys.goals, 'flat'], queryFn: () => goalsApi.list() });
  const [f, setF] = useState({
    title: goal?.title ?? '',
    description: goal?.description ?? '',
    level: goal?.level ?? ('CUSTOM' as GoalLevel),
    parentId: goal?.parent_id ?? parentId ?? '',
    type: goal?.progress_type ?? ('MILESTONES' as ProgressType),
    unit: goal?.metric_unit ?? '',
    startValue: goal?.start_value ? String(Number(goal.start_value)) : '',
    targetValue: goal?.target_value ? String(Number(goal.target_value)) : '',
    start: goal?.start_date ?? today,
    target: goal?.target_date ?? '',
    categoryId: goal?.category_id ?? '',
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const save = useMutation({
    mutationFn: () => {
      const input: GoalInput = {
        title: f.title.trim(),
        description: f.description,
        level: f.level,
        parent_id: f.parentId || null,
        progress_type: f.type,
        metric_unit: f.unit.trim(),
        start_value: f.type === 'METRIC' ? f.startValue : null,
        target_value: f.type === 'METRIC' ? f.targetValue : null,
        start_date: f.start,
        target_date: f.target || null,
        category_id: f.categoryId || null,
      };
      return goal ? goalsApi.update(goal.id, input) : goalsApi.create(input);
    },
    onSuccess: (g) => {
      onClose();
      if (!goal) navigate(`/goals/${g.id}`);
    },
    onSettled: invalidate,
  });
  const errors = save.error instanceof ApiError ? save.error.fieldErrors() : {};
  const parents = (all.data ?? []).filter((g) => g.id !== goal?.id);
  const metricInvalid =
    f.type === 'METRIC' && (!f.startValue || !f.targetValue || f.startValue === f.targetValue);

  return (
    <>
      <TextField
        label={t('editor.title')}
        value={f.title}
        onChange={(e) => set('title', e.target.value)}
        placeholder={t('editor.titlePlaceholder')}
        error={errors.title}
        maxLength={200}
        data-autofocus
      />
      <TextArea
        label={t('editor.description')}
        value={f.description}
        onChange={(e) => set('description', e.target.value)}
        rows={2}
      />
      <div className={styles.formGrid}>
        <SelectField
          label={t('editor.level')}
          value={f.level}
          onChange={(e) => set('level', e.target.value as GoalLevel)}
          options={LEVELS.map((l) => ({ value: l, label: t(`level.${l}`) }))}
        />
        <SelectField
          label={t('editor.parent')}
          value={f.parentId}
          onChange={(e) => set('parentId', e.target.value)}
          options={[
            { value: '', label: t('editor.noParent') },
            ...parents.map((g) => ({ value: g.id, label: g.title })),
          ]}
          error={errors.parent_id}
        />
      </div>
      <div>
        <p className={styles.subtle}>{t('editor.progressType')}</p>
        <div className={styles.pills} role="radiogroup" aria-label={t('editor.progressType')}>
          {TYPES.map((type) => (
            <button
              key={type}
              type="button"
              role="radio"
              aria-checked={f.type === type}
              onClick={() => set('type', type)}
            >
              {t(`progressType.${type}`)}
            </button>
          ))}
        </div>
        <p className={styles.subtle}>{t(`progressHint.${f.type}`)}</p>
      </div>
      {f.type === 'METRIC' ? (
        <div className={styles.formGrid}>
          <TextField
            label={t('editor.startValue')}
            type="number"
            step="any"
            value={f.startValue}
            onChange={(e) => set('startValue', e.target.value)}
          />
          <TextField
            label={t('editor.targetValue')}
            type="number"
            step="any"
            value={f.targetValue}
            onChange={(e) => set('targetValue', e.target.value)}
            error={errors.target_value}
          />
          <TextField
            label={t('editor.unit')}
            value={f.unit}
            onChange={(e) => set('unit', e.target.value)}
            placeholder={t('editor.unitPlaceholder')}
            maxLength={20}
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
        <TextField
          label={t('editor.target')}
          type="date"
          value={f.target}
          min={f.start}
          onChange={(e) => set('target', e.target.value)}
          error={errors.target_date}
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
      {save.error ? <Alert>{errorMessage(save.error)}</Alert> : null}
      <div className={styles.row} style={{ justifyContent: 'flex-end' }}>
        <Button variant="ghost" onClick={onClose}>
          {t('editor.cancel')}
        </Button>
        <Button
          loading={save.isPending}
          disabled={!f.title.trim() || metricInvalid}
          onClick={() => save.mutate()}
        >
          {t('editor.save')}
        </Button>
      </div>
    </>
  );
}
