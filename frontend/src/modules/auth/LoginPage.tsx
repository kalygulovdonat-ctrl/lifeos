import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowRight, LockKeyhole, Mail } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router';

import { authApi } from '@/shared/api/auth';
import { Alert, Button, TextField } from '@/shared/components/ui';
import { useErrorMessage } from '@/shared/hooks/useErrorMessage';
import { syncPreferences } from '@/shared/hooks/useSession';
import { useAuthStore } from '@/shared/store/authStore';

import styles from './auth.module.css';
import { loginSchema, PASSWORD_MIN, type LoginValues } from './schemas';

export default function LoginPage() {
  const { t } = useTranslation('auth');
  const toMessage = useErrorMessage();
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const { access, profile } = await authApi.login(values);
      useAuthStore.getState().setSession(access, profile);
      syncPreferences(profile);
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      navigate(from && from !== '/login' ? from : '/', { replace: true });
    } catch (error) {
      setFormError(toMessage(error));
    }
  });

  return (
    <form className={styles.form} onSubmit={onSubmit} noValidate>
      <div className={styles.heading}>
        <h1>{t('login.title')}</h1>
        <p>{t('login.subtitle')}</p>
      </div>
      {formError ? <Alert>{formError}</Alert> : null}
      <TextField
        label={t('fields.email')}
        type="email"
        autoComplete="email"
        autoFocus
        placeholder="you@example.com"
        icon={<Mail size={16} />}
        error={errors.email?.message && t(errors.email.message)}
        {...register('email')}
      />
      <TextField
        label={t('fields.password')}
        type="password"
        autoComplete="current-password"
        icon={<LockKeyhole size={16} />}
        error={errors.password?.message && t(errors.password.message, { count: PASSWORD_MIN })}
        {...register('password')}
      />
      <Button
        type="submit"
        size="lg"
        block
        loading={isSubmitting}
        icon={isSubmitting ? undefined : <ArrowRight size={17} />}
        className={styles.submit}
      >
        {t('login.submit')}
      </Button>
      <p className={styles.switch}>
        {t('login.noAccount')} <Link to="/register">{t('login.toRegister')}</Link>
      </p>
    </form>
  );
}
