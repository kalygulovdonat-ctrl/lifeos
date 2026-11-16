import { zodResolver } from '@hookform/resolvers/zod';
import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { ApiError } from '@/shared/api/client';
import { authApi } from '@/shared/api/auth';
import type { Language } from '@/shared/api/types';
import { Alert, Button, Card, SelectField, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { syncPreferences } from '@/shared/hooks/useSession';
import { useAuthStore } from '@/shared/store/authStore';
import { browserTimezone, supportedTimezones } from '@/shared/utils/datetime';

import styles from './auth.module.css';
import { PASSWORD_MIN, registerSchema, type RegisterValues } from './schemas';

export default function RegisterPage() {
  const { t, i18n } = useTranslation('auth');
  const toMessage = useErrorMessage();
  const navigate = useNavigate();
  const [formError, setFormError] = useState<string | null>(null);
  const timezones = useMemo(() => supportedTimezones().map((tz) => ({ value: tz, label: tz })), []);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { timezone: browserTimezone(), language: i18n.language as Language },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      // The language picked in the switcher on this page wins over the initial default.
      const { access, profile } = await authApi.register({
        ...values,
        language: i18n.language as Language,
      });
      useAuthStore.getState().setSession(access, profile);
      syncPreferences(profile);
      navigate('/', { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.code === 'VALIDATION_ERROR') {
        for (const [field, message] of Object.entries(error.fieldErrors())) {
          if (field in values) setError(field as keyof RegisterValues, { message });
        }
      }
      setFormError(toMessage(error));
    }
  });

  const fieldError = (message?: string) =>
    message ? t(message, { count: PASSWORD_MIN, defaultValue: message }) : undefined;

  return (
    <Card>
      <form className={styles.form} onSubmit={onSubmit} noValidate>
        <div className={styles.heading}>
          <h1>{t('register.title')}</h1>
        </div>
        {formError ? <Alert>{formError}</Alert> : null}
        <TextField
          label={t('fields.displayName')}
          autoComplete="name"
          autoFocus
          error={fieldError(errors.display_name?.message)}
          {...register('display_name')}
        />
        <TextField
          label={t('fields.email')}
          type="email"
          autoComplete="email"
          error={fieldError(errors.email?.message)}
          {...register('email')}
        />
        <TextField
          label={t('fields.password')}
          type="password"
          autoComplete="new-password"
          error={fieldError(errors.password?.message)}
          {...register('password')}
        />
        <SelectField
          label={t('fields.timezone')}
          options={timezones}
          error={fieldError(errors.timezone?.message)}
          {...register('timezone')}
        />
        <Button type="submit" block loading={isSubmitting}>
          {t('register.submit')}
        </Button>
        <p className={styles.switch}>
          {t('register.hasAccount')} <Link to="/login">{t('register.toLogin')}</Link>
        </p>
      </form>
    </Card>
  );
}
