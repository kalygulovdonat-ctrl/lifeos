import { zodResolver } from '@hookform/resolvers/zod';
import {
  CalendarDays,
  Check,
  Clock,
  Globe,
  Languages,
  Monitor,
  Moon,
  Palette,
  Sun,
  SunMedium,
  Sunrise,
  Sunset,
  UserRound,
} from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { ApiError } from '@/shared/api/client';
import { profileApi } from '@/shared/api/auth';
import { LANGUAGES, type Profile } from '@/shared/api/types';
import {
  Alert,
  Button,
  Card,
  IconTile,
  PageHeader,
  SegmentedControl,
  SelectField,
  TextField,
} from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { syncPreferences } from '@/shared/hooks/useSession';
import { useAuthStore } from '@/shared/store/authStore';
import { clockOptions, supportedTimezones } from '@/shared/utils/datetime';

import { SettingsTabs } from './CategoriesSettingsPage';
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
/** Form state as the inputs hold it (select values arrive as strings). */
type FormValues = z.input<typeof schema>;
/** Parsed result handed to onSubmit (week_start coerced to a number). */
type Values = z.output<typeof schema>;

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
    watch,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FormValues, unknown, Values>({
    resolver: zodResolver(schema),
    values: profile ? toValues(profile) : undefined,
  });

  if (!profile) return null;
  // Live preview: the clock lists follow the 12/24-hour choice before it is saved.
  const timeFormat = watch('time_format') ?? profile.time_format;

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

  const section = (icon: ReactNode, key: string, body: ReactNode) => (
    <Card className={styles.section}>
      <div className={styles.sectionIntro}>
        <IconTile size={38}>{icon}</IconTile>
        <div>
          <h2>{t(`sections.${key}.title`)}</h2>
          <p>{t(`sections.${key}.description`)}</p>
        </div>
      </div>
      <div className={styles.fields}>{body}</div>
    </Card>
  );

  return (
    <form className={styles.page} onSubmit={onSubmit} noValidate>
      <PageHeader title={t('title')} description={t('subtitle')} />
      <SettingsTabs />
      {status === 'error' && errorText ? <Alert>{errorText}</Alert> : null}

      {section(
        <UserRound size={19} />,
        'profile',
        <div className={styles.grid}>
          <TextField
            label={t('profile.displayName')}
            error={err('display_name')}
            {...register('display_name')}
          />
          <TextField label={t('profile.email')} value={profile.email} readOnly disabled />
        </div>,
      )}

      {section(
        <Globe size={19} />,
        'region',
        <div className={styles.grid}>
          <SelectField
            label={t('profile.language')}
            icon={<Languages size={16} />}
            options={LANGUAGES.map((l) => ({ value: l, label: LANGUAGE_NAMES[l] }))}
            {...register('language')}
          />
          <SelectField
            label={t('profile.timezone')}
            icon={<Clock size={16} />}
            options={timezones}
            error={err('timezone')}
            {...register('timezone')}
          />
          <SegmentedControl
            label={t('profile.timeFormat')}
            options={[
              { value: '24h', label: t('profile.timeFormat24') },
              { value: '12h', label: t('profile.timeFormat12') },
            ]}
            registration={register('time_format')}
          />
          <SelectField
            label={t('profile.weekStart')}
            icon={<CalendarDays size={16} />}
            options={[1, 2, 3, 4, 5, 6, 7].map((d) => ({
              value: String(d),
              label: t(`weekdays.${d}`),
            }))}
            {...register('week_start')}
          />
        </div>,
      )}

      {section(
        <Palette size={19} />,
        'appearance',
        <SegmentedControl
          label={t('profile.theme')}
          options={[
            { value: 'light', label: t('profile.themeLight'), icon: <Sun size={15} /> },
            { value: 'dark', label: t('profile.themeDark'), icon: <Moon size={15} /> },
            { value: 'system', label: t('profile.themeSystem'), icon: <Monitor size={15} /> },
          ]}
          registration={register('theme')}
        />,
      )}

      {section(
        <SunMedium size={19} />,
        'day',
        <div className={styles.grid}>
          <SelectField
            label={t('profile.dayStart')}
            icon={<Sunrise size={16} />}
            options={clockOptions(timeFormat, watch('day_start_time'))}
            error={err('day_start_time')}
            {...register('day_start_time')}
          />
          <SelectField
            label={t('profile.dayEnd')}
            icon={<Sunset size={16} />}
            options={clockOptions(timeFormat, watch('day_end_time'))}
            hint={t('profile.dayWindowHint')}
            error={err('day_end_time')}
            {...register('day_end_time')}
          />
        </div>,
      )}

      <div className={[styles.saveBar, isDirty ? styles.saveBarActive : ''].join(' ')}>
        <span className={styles.saveHint} role="status">
          {isDirty ? t('unsaved') : status === 'saved' ? tc('status.saved') : t('allSaved')}
        </span>
        <div className={styles.saveActions}>
          {isDirty ? (
            <Button variant="ghost" onClick={() => reset()}>
              {tc('actions.cancel')}
            </Button>
          ) : null}
          <Button
            type="submit"
            loading={isSubmitting}
            disabled={!isDirty}
            icon={<Check size={16} />}
          >
            {tc('actions.save')}
          </Button>
        </div>
      </div>
    </form>
  );
}
