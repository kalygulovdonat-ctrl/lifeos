import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Archive, Check, Pencil, Plus, Tags, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router';

import { useCategories } from '@/modules/planning/hooks';
import { categoriesApi, keys } from '@/shared/api/planning';
import type { Category } from '@/shared/api/types';
import { Alert, Button, Card, PageHeader } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';

import styles from './settings.module.css';

const PALETTE = [
  '#3B82F6',
  '#8B5CF6',
  '#EC4899',
  '#EF4444',
  '#F97316',
  '#EAB308',
  '#10B981',
  '#14B8A6',
  '#64748B',
];

export function SettingsTabs() {
  const { t } = useTranslation('settings');
  return (
    <nav className={styles.tabs} aria-label={t('title')}>
      <NavLink to="/settings/profile">{t('tabs.profile')}</NavLink>
      <NavLink to="/settings/categories">{t('tabs.categories')}</NavLink>
    </nav>
  );
}

export default function CategoriesSettingsPage() {
  const { t } = useTranslation('settings');
  const qc = useQueryClient();
  const errorMessage = useErrorMessage();
  const { categories, label } = useCategories();
  const [name, setName] = useState('');
  const [color, setColor] = useState(PALETTE[0]!);
  const refresh = () => void qc.invalidateQueries({ queryKey: keys.categories });

  const create = useMutation({
    mutationFn: () => categoriesApi.create({ name: name.trim(), color }),
    onSuccess: () => setName(''),
    onSettled: refresh,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim()) create.mutate();
  };

  return (
    <div className={styles.page}>
      <PageHeader title={t('title')} description={t('categories.subtitle')} />
      <SettingsTabs />
      <Card>
        <form className={styles.catForm} onSubmit={submit}>
          <Swatches value={color} onChange={setColor} />
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('categories.placeholder')}
            aria-label={t('categories.placeholder')}
            maxLength={60}
          />
          <Button
            type="submit"
            size="sm"
            icon={<Plus size={15} />}
            disabled={!name.trim()}
            loading={create.isPending}
          >
            {t('categories.add')}
          </Button>
        </form>
        {create.error ? <Alert>{errorMessage(create.error)}</Alert> : null}
        <ul className={styles.catList}>
          {categories.map((c) => (
            <CategoryItem key={c.id} category={c} label={label(c)} onChanged={refresh} />
          ))}
        </ul>
        {!categories.length ? (
          <p className={styles.catEmpty}>
            <Tags size={16} /> {t('categories.empty')}
          </p>
        ) : null}
      </Card>
    </div>
  );
}

function Swatches({ value, onChange }: { value: string; onChange: (c: string) => void }) {
  const { t } = useTranslation('settings');
  return (
    <div className={styles.swatches} role="radiogroup" aria-label={t('categories.color')}>
      {PALETTE.map((c) => (
        <button
          key={c}
          type="button"
          role="radio"
          aria-checked={value.toUpperCase() === c}
          aria-label={c}
          style={{ background: c }}
          onClick={() => onChange(c)}
        />
      ))}
    </div>
  );
}

function CategoryItem({
  category,
  label,
  onChanged,
}: {
  category: Category;
  label: string;
  onChanged: () => void;
}) {
  const { t } = useTranslation('settings');
  const errorMessage = useErrorMessage();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(label);
  const [color, setColor] = useState(category.color);
  const update = useMutation({
    mutationFn: () =>
      categoriesApi.update(category.id, {
        color,
        ...(name.trim() !== label ? { name: name.trim() } : {}),
      }),
    onSuccess: () => setEditing(false),
    onSettled: onChanged,
  });
  const archive = useMutation({
    mutationFn: () => categoriesApi.archive(category.id),
    onSettled: onChanged,
  });

  if (editing) {
    return (
      <li className={styles.catItem} data-editing>
        <Swatches value={color} onChange={setColor} />
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={60}
          aria-label={t('categories.name')}
          autoFocus
        />
        <button
          type="button"
          onClick={() => update.mutate()}
          aria-label={t('categories.save')}
          disabled={!name.trim()}
        >
          <Check size={16} />
        </button>
        <button type="button" onClick={() => setEditing(false)} aria-label={t('categories.cancel')}>
          <X size={16} />
        </button>
        {update.error ? (
          <span className={styles.catError}>{errorMessage(update.error)}</span>
        ) : null}
      </li>
    );
  }
  return (
    <li className={styles.catItem}>
      <i style={{ background: category.color }} aria-hidden="true" />
      <span>{label}</span>
      <button type="button" onClick={() => setEditing(true)} aria-label={t('categories.edit')}>
        <Pencil size={15} />
      </button>
      <button type="button" onClick={() => archive.mutate()} aria-label={t('categories.archive')}>
        <Archive size={15} />
      </button>
    </li>
  );
}
