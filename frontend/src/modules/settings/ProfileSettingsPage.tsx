import { zodResolver } from '@hookform/resolvers/zod';
import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { ApiError } from '@/shared/api/client';
import { profileApi } from '@/shared/api/auth';
import { LANGUAGES, type Profile } from '@/shared/api/types';
import { Alert, Button, Card, SelectField, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { syncPreferences } from '@/shared/hooks/useSession';
import { useAuthStore } from '@/shared/store/authStore';
import { supportedTimezones } from '@/shared/utils/datetime';

import styles from './settings.module.css';

const schema = z
  .object({
    display_name: z.string().trim().min(1).max(80),
    language: z.enum(LANGUAGES),
    timezone: z.string().min(1),
    time_format: z.enum(['12h', '24h']),
    week_start: z.coerce.number().int().min(1).max(7),
    theme: z.enum(['light', 'dark', 'system']),
    day_start_time: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/),
    day_end_time: z.string().regex(/^\d{2}:\d{2}(:\d{2})?$/),
  })
  .refine((v) => v.day_end_time.slice(0, 5) > v.day_start_time.slice(0, 5), {
    path: ['day_end_time'],
    message: 'day_end_time',
  });
type Values = z.infer<typeof schema>;

const LANGUAGE_NAMES = { ru: 'Русский', en: 'English', ky: 'Кыргызча' } as const;

function toValues(p: Profile): Values {
  return {
    display_name: p.display_name,
    language: p.language,
    timezone: p.timezone,
    time_format: p.time_format,
    week_start: p.week_start,
    theme: p.theme,
    day_start_time: p.day_start_time.slice(0, 5),
    day_end_time: p.day_end_time.slice(0, 5),
  };
}

export default function ProfileSettingsPage() {
  const { t } = useTranslation('settings');
  const { t: tc } = useTranslation('common');
  const toMessage = useErrorMessage();
  const profile = useAuthStore((s) => s.profile);
  const [status, setStatus] = useState<'idle' | 'saved' | 'error'>('idle');
  const [errorText, setErrorText] = useState<string | null>(null);
  const timezones = useMemo(() => supportedTimezones().map((tz) => ({ value: tz, label: tz })), []);

  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    values: profile ? toValues(profile) : undefined,
  });

  if (!profile) return null;

  const onSubmit = handleSubmit(async (values) => {
    setStatus('idle');
    try {
      const updated = await profileApi.update(values);
      useAuthStore.getState().setProfile(updated);
      syncPreferences(updated);
      reset(toValues(updated));
      setStatus('saved');
    } catch (error) {
      if (error instanceof ApiError) {
        for (const [field, message] of Object.entries(error.fieldErrors())) {
          if (field in values) setError(field as keyof Values, { message });
        }
      }
      setErrorText(toMessage(error));
      setStatus('error');
    }
  });

  const err = (key: keyof Values) => (errors[key] ? tc('errors.VALIDATION_ERROR') : undefined);

  return (
    <div className={styles.page}>
      <h1>{t('title')}</h1>
      <Card>
        <form className={styles.form} onSubmit={onSubmit} noValidate>
          <h2 className={styles.sectionTitle}>{t('profile.title')}</h2>
          {status === 'error' && errorText ? <Alert>{errorText}</Alert> : null}
          <div className={styles.grid}>
            <TextField label={t('profile.email')} value={profile.email} readOnly disabled />
            <TextField
              label={t('profile.displayName')}
              error={err('display_name')}
              {...register('display_name')}
            />
            <SelectField
              label={t('profile.language')}
              options={LANGUAGES.map((l) => ({ value: l, label: LANGUAGE_NAMES[l] }))}
              {...register('language')}
            />
            <SelectField
              label={t('profile.timezone')}
              options={timezones}
              error={err('timezone')}
              {...register('timezone')}
            />
            <SelectField
              label={t('profile.timeFormat')}
              options={[
                { value: '24h', label: t('profile.timeFormat24') },
                { value: '12h', label: t('profile.timeFormat12') },
              ]}
              {...register('time_format')}
            />
            <SelectField
              label={t('profile.weekStart')}
              options={[1, 2, 3, 4, 5, 6, 7].map((d) => ({
                value: String(d),
                label: t(`weekdays.${d}`),
              }))}
              {...register('week_start')}
            />
            <SelectField
              label={t('profile.theme')}
              options={[
                { value: 'system', label: t('profile.themeSystem') },
                { value: 'light', label: t('profile.themeLight') },
                { value: 'dark', label: t('profile.themeDark') },
              ]}
              {...register('theme')}
            />
            <div />
            <TextField
              label={t('profile.dayStart')}
              type="time"
              error={err('day_start_time')}
              {...register('day_start_time')}
            />
            <TextField
              label={t('profile.dayEnd')}
              type="time"
              hint={t('profile.dayWindowHint')}
              error={err('day_end_time')}
              {...register('day_end_time')}
            />
          </div>
          <div className={styles.actions}>
            {status === 'saved' && !isDirty ? (
              <span role="status" className={styles.saved}>
                {tc('status.saved')}
              </span>
            ) : null}
            <Button type="submit" loading={isSubmitting} disabled={!isDirty}>
              {tc('actions.save')}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
